"""The bake-off.

Clones every prepared reference on all three providers, has each clone read the
same test sentence three times, and records first-byte and total latency for
every generation.

Three runs per case because a single latency sample is noise: cold starts,
network jitter, and routing all move it. Medians are reported.

Every voice created here is deleted at the end. The generated audio is kept.
"""

import json
import os
import statistics
import subprocess
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()
ROOT = Path(__file__).parent
PREPARED = ROOT / "refs_prepared"
AUDIO = ROOT / "site" / "audio"

cases = json.loads((ROOT / "cases.json").read_text())
TEXT = cases["test_sentence"]
RUNS = cases["runs_per_case"]

FISH = os.environ["FISH_API_KEY"]
ELEVEN = os.environ["ELEVENLABS_API_KEY"]
CARTESIA = os.environ["CARTESIA_API_KEY"]
CVER = "2025-04-16"

created = []   # (provider, voice_id) for cleanup
rows = []


def timed_stream(ctx, dest):
    """Stream a response to disk, returning (first-byte seconds, total seconds, bytes)."""
    t0 = time.perf_counter()
    ttfb, n = None, 0
    with open(dest, "wb") as f, ctx as r:
        r.raise_for_status()
        for chunk in r.iter_bytes():
            if chunk:
                if ttfb is None:
                    ttfb = time.perf_counter() - t0
                f.write(chunk)
                n += len(chunk)
    return ttfb, time.perf_counter() - t0, n


# ---------------------------------------------------------------- providers

def fish_clone(audio, label):
    from fish_audio_sdk import Session
    # enhance_audio_quality=False: Fish cleans up reference audio by default,
    # which would repair the phone track while the other two providers receive
    # it raw. That would destroy the studio-vs-phone comparison.
    m = Session(FISH).create_model(
        title=label, visibility="private", voices=[audio], enhance_audio_quality=False
    )
    return m.id


def fish_gen(vid, dest):
    from fish_audio_sdk import Session, TTSRequest
    s = Session(FISH)
    t0 = time.perf_counter()
    ttfb, n = None, 0
    with open(dest, "wb") as f:
        for chunk in s.tts(TTSRequest(text=TEXT, reference_id=vid), backend="s2.1-pro"):
            if chunk:
                if ttfb is None:
                    ttfb = time.perf_counter() - t0
                f.write(chunk)
                n += len(chunk)
    return ttfb, time.perf_counter() - t0, n


def eleven_clone(audio, label):
    r = httpx.post(
        "https://api.elevenlabs.io/v1/voices/add",
        headers={"xi-api-key": ELEVEN},
        data={"name": label},
        files=[("files", ("ref.wav", audio, "audio/wav"))],
        timeout=180,
    )
    r.raise_for_status()
    return r.json()["voice_id"]


def eleven_gen(vid, dest):
    return timed_stream(httpx.stream(
        "POST", f"https://api.elevenlabs.io/v1/text-to-speech/{vid}/stream",
        headers={"xi-api-key": ELEVEN},
        json={"text": TEXT, "model_id": "eleven_multilingual_v2"},
        timeout=180), dest)


def cartesia_clone(audio, label):
    r = httpx.post(
        "https://api.cartesia.ai/voices/clone",
        headers={"X-API-Key": CARTESIA, "Cartesia-Version": CVER},
        data={"name": label, "language": "en", "mode": "similarity"},
        files=[("clip", ("ref.wav", audio, "audio/wav"))],
        timeout=180,
    )
    r.raise_for_status()
    return r.json()["id"]


def cartesia_gen(vid, dest):
    return timed_stream(httpx.stream(
        "POST", "https://api.cartesia.ai/tts/bytes",
        headers={"X-API-Key": CARTESIA, "Cartesia-Version": CVER},
        json={"model_id": "sonic-2", "transcript": TEXT,
              "voice": {"mode": "id", "id": vid},
              "output_format": {"container": "mp3", "sample_rate": 44100, "bit_rate": 128000},
              "language": "en"},
        timeout=180), dest)


PROVIDERS = {
    "fish": (fish_clone, fish_gen),
    "elevenlabs": (eleven_clone, eleven_gen),
    "cartesia": (cartesia_clone, cartesia_gen),
}

# ---------------------------------------------------------------- the run

for p in PROVIDERS:
    (AUDIO / p).mkdir(parents=True, exist_ok=True)
(AUDIO / "reference").mkdir(parents=True, exist_ok=True)

# Optional filter: `python run.py phone` re-runs only that capture. Results are
# merged into results.json rather than replacing it, so a partial re-run does not
# silently destroy the rows it did not touch.
import sys
only = set(sys.argv[1:])

targets = []
for sp in cases["speakers"]:
    for cap in cases["captures"]:
        if only and cap["id"] not in only and sp["id"] not in only:
            continue
        ref = PREPARED / f"{sp['id']}-{cap['id']}.wav"
        if ref.exists():
            targets.append((sp, cap, ref))

print(f'Test sentence ({len(TEXT)} chars): "{TEXT}"')
print(f"{len(targets)} references x {len(PROVIDERS)} providers x {RUNS} runs "
      f"= {len(targets) * len(PROVIDERS) * RUNS} generations\n")

for sp, cap, ref in targets:
    key = f"{sp['id']}-{cap['id']}"
    audio = ref.read_bytes()

    # Short published clip of the original, so full family recordings stay private.
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(ref), "-t", "10",
         "-c:a", "libmp3lame", "-b:a", "128k", str(AUDIO / "reference" / f"{key}.mp3")],
        check=True)

    for pname, (clone_fn, gen_fn) in PROVIDERS.items():
        try:
            t0 = time.perf_counter()
            vid = clone_fn(audio, f"bakeoff-{key}")
            clone_s = time.perf_counter() - t0
            created.append((pname, vid))

            ttfbs, totals, size = [], [], 0
            for i in range(RUNS):
                # Keep run 1 as the published file; later runs only supply timings.
                dest = (AUDIO / pname / f"{key}.mp3") if i == 0 else (ROOT / ".scratch" / f"{key}-{pname}-{i}.mp3")
                dest.parent.mkdir(parents=True, exist_ok=True)
                ttfb, total, n = gen_fn(vid, dest)
                ttfbs.append(ttfb)
                totals.append(total)
                if i == 0:
                    size = n

            rows.append({
                "speaker": sp["id"], "speaker_label": sp["label"], "accent": sp["accent"],
                "role": sp["role"], "capture": cap["id"], "capture_label": cap["label"],
                "provider": pname, "chars": len(TEXT), "clone_seconds": round(clone_s, 2),
                "ttfb_ms": [round(t * 1000) for t in ttfbs],
                "total_s": [round(t, 3) for t in totals],
                "ttfb_median_ms": round(statistics.median(ttfbs) * 1000),
                "total_median_s": round(statistics.median(totals), 3),
                "bytes": size, "audio": f"audio/{pname}/{key}.mp3",
            })
            print(f"  {key:16} {pname:11} clone {clone_s:5.1f}s | "
                  f"first byte median {statistics.median(ttfbs) * 1000:6.0f}ms | "
                  f"total median {statistics.median(totals):5.2f}s")
        except httpx.HTTPStatusError as e:
            print(f"  {key:16} {pname:11} HTTP {e.response.status_code}: {e.response.text[:150]}")
        except Exception as e:
            print(f"  {key:16} {pname:11} FAILED {type(e).__name__}: {str(e)[:150]}")
    print()

# Fish publishes $15 per million characters. ElevenLabs and Cartesia bill against
# monthly subscription credits, so an equivalent per-character price depends on
# how much of the plan you use. Recording characters and leaving those null is
# more honest than inventing a comparable rate.
for r in rows:
    r["cost_usd"] = round(r["chars"] / 1_000_000 * 15.0, 6) if r["provider"] == "fish" else None

RESULTS = ROOT / "results.json"
existing = json.loads(RESULTS.read_text())["results"] if RESULTS.exists() else []
fresh = {(r["speaker"], r["capture"], r["provider"]) for r in rows}
merged = [r for r in existing if (r["speaker"], r["capture"], r["provider"]) not in fresh] + rows

RESULTS.write_text(json.dumps({
    "test_sentence": TEXT, "runs_per_case": RUNS, "results": merged,
}, indent=2))

print(f"{len(rows)} rows written, {len(merged)} total in results.json")

print("\nDeleting the voices created by this run...")
for prov, vid in created:
    try:
        if prov == "fish":
            from fish_audio_sdk import Session
            Session(FISH).delete_model(vid)
        elif prov == "elevenlabs":
            httpx.delete(f"https://api.elevenlabs.io/v1/voices/{vid}",
                         headers={"xi-api-key": ELEVEN}, timeout=60)
        else:
            httpx.delete(f"https://api.cartesia.ai/voices/{vid}",
                         headers={"X-API-Key": CARTESIA, "Cartesia-Version": CVER}, timeout=60)
    except Exception as e:
        print(f"  could not delete {prov} {vid}: {e}")
print(f"  {len(created)} voices removed")
