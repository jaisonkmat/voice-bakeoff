"""Clone one reference on all three providers and generate the test sentence.

Purpose is to surface API surprises before the real run, not to produce results.
Measures time to first audio byte separately from total time, because on a phone
call the caller hears silence until byte one arrives, so first-byte is the
latency a customer actually perceives.

Cleans up after itself: every voice created here is deleted at the end.
"""

import json
import os
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()
ROOT = Path(__file__).parent
cases = json.loads((ROOT / "cases.json").read_text())
TEXT = cases["test_sentence"]
REF = ROOT / "refs_prepared" / "mom-studio.wav"
OUT = ROOT / ".scratch"
OUT.mkdir(exist_ok=True)

FISH = os.environ["FISH_API_KEY"]
ELEVEN = os.environ["ELEVENLABS_API_KEY"]
CARTESIA = os.environ["CARTESIA_API_KEY"]
CARTESIA_VER = "2025-04-16"

audio_bytes = REF.read_bytes()
cleanup = []


def stream_to_file(req_ctx, dest):
    """Return (time to first byte, total time, bytes written)."""
    t0 = time.perf_counter()
    ttfb = None
    n = 0
    with open(dest, "wb") as f, req_ctx as r:
        r.raise_for_status()
        for chunk in r.iter_bytes():
            if chunk:
                if ttfb is None:
                    ttfb = time.perf_counter() - t0
                f.write(chunk)
                n += len(chunk)
    return ttfb, time.perf_counter() - t0, n


def fish():
    from fish_audio_sdk import Session, TTSRequest
    s = Session(FISH)
    t0 = time.perf_counter()
    # enhance_audio_quality=False: Fish cleans up reference audio by default.
    # Leaving it on would repair the phone track while the other two providers
    # receive it raw, which would destroy the studio-vs-phone comparison.
    model = s.create_model(
        title="bakeoff-smoketest", visibility="private",
        voices=[audio_bytes], enhance_audio_quality=False,
    )
    clone_s = time.perf_counter() - t0
    cleanup.append(("fish", model.id))

    dest = OUT / "smoke-fish.mp3"
    t0 = time.perf_counter()
    ttfb, n = None, 0
    with open(dest, "wb") as f:
        for chunk in s.tts(TTSRequest(text=TEXT, reference_id=model.id), backend="s2.1-pro"):
            if chunk:
                if ttfb is None:
                    ttfb = time.perf_counter() - t0
                f.write(chunk)
                n += len(chunk)
    return clone_s, ttfb, time.perf_counter() - t0, n, dest


def elevenlabs():
    t0 = time.perf_counter()
    r = httpx.post(
        "https://api.elevenlabs.io/v1/voices/add",
        headers={"xi-api-key": ELEVEN},
        data={"name": "bakeoff-smoketest"},
        files=[("files", ("ref.wav", audio_bytes, "audio/wav"))],
        timeout=180,
    )
    r.raise_for_status()
    vid = r.json()["voice_id"]
    clone_s = time.perf_counter() - t0
    cleanup.append(("elevenlabs", vid))

    dest = OUT / "smoke-elevenlabs.mp3"
    ctx = httpx.stream(
        "POST", f"https://api.elevenlabs.io/v1/text-to-speech/{vid}/stream",
        headers={"xi-api-key": ELEVEN},
        json={"text": TEXT, "model_id": "eleven_multilingual_v2"},
        timeout=180,
    )
    ttfb, total, n = stream_to_file(ctx, dest)
    return clone_s, ttfb, total, n, dest


def cartesia():
    h = {"X-API-Key": CARTESIA, "Cartesia-Version": CARTESIA_VER}
    t0 = time.perf_counter()
    r = httpx.post(
        "https://api.cartesia.ai/voices/clone",
        headers=h,
        data={"name": "bakeoff-smoketest", "language": "en", "mode": "similarity"},
        files=[("clip", ("ref.wav", audio_bytes, "audio/wav"))],
        timeout=180,
    )
    r.raise_for_status()
    vid = r.json()["id"]
    clone_s = time.perf_counter() - t0
    cleanup.append(("cartesia", vid))

    dest = OUT / "smoke-cartesia.mp3"
    ctx = httpx.stream(
        "POST", "https://api.cartesia.ai/tts/bytes",
        headers=h,
        json={
            "model_id": "sonic-2",
            "transcript": TEXT,
            "voice": {"mode": "id", "id": vid},
            "output_format": {"container": "mp3", "sample_rate": 44100, "bit_rate": 128000},
            "language": "en",
        },
        timeout=180,
    )
    ttfb, total, n = stream_to_file(ctx, dest)
    return clone_s, ttfb, total, n, dest


print(f'Reference: {REF.name} ({len(audio_bytes):,} bytes)')
print(f'Text: "{TEXT}" ({len(TEXT)} chars)\n')

for name, fn in [("fish", fish), ("elevenlabs", elevenlabs), ("cartesia", cartesia)]:
    try:
        clone_s, ttfb, total, n, dest = fn()
        print(f"{name:12} OK  clone {clone_s:5.1f}s | first byte {ttfb * 1000:6.0f}ms | "
              f"total {total:5.2f}s | {n:,} bytes -> {dest.name}")
    except httpx.HTTPStatusError as e:
        print(f"{name:12} HTTP {e.response.status_code}: {e.response.text[:220]}")
    except Exception as e:
        print(f"{name:12} FAILED {type(e).__name__}: {str(e)[:220]}")

print("\nCleaning up test voices...")
for prov, vid in cleanup:
    try:
        if prov == "fish":
            from fish_audio_sdk import Session
            Session(FISH).delete_model(vid)
        elif prov == "elevenlabs":
            httpx.delete(f"https://api.elevenlabs.io/v1/voices/{vid}",
                         headers={"xi-api-key": ELEVEN}, timeout=60)
        else:
            httpx.delete(f"https://api.cartesia.ai/voices/{vid}",
                         headers={"X-API-Key": CARTESIA, "Cartesia-Version": CARTESIA_VER}, timeout=60)
        print(f"  deleted {prov} {vid}")
    except Exception as e:
        print(f"  could not delete {prov} {vid}: {e}")
