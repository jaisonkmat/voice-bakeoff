"""Turn raw recordings into uniform cloning references.

Every provider must receive a byte-identical input, so all normalization happens
here rather than being left to each API. Four operations, applied the same way
to every file:

  1. Trim to the same window length (cases.json -> reference_seconds)
  2. Downmix to mono, so no provider makes its own stereo decision
  3. Resample to 48kHz
  4. Loudness-match with two-pass EBU R128 in LINEAR mode

Linear mode matters: it applies one constant gain to the whole file. No
compression, no limiting, no change to dynamics. Mathematically identical to
moving a fader, just measured rather than eyeballed.

Deliberately NOT done: EQ, noise reduction, de-essing. The phone track being
thinner and noisier than the studio track is the variable under test. Cleaning
it up would destroy the comparison.
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
REFS = ROOT / "refs"
OUT = ROOT / "refs_prepared"
TARGET_LUFS = -20.0

cases = json.loads((ROOT / "cases.json").read_text())
SECONDS = cases["reference_seconds"]


def measure_loudness(path):
    """Measure integrated loudness of a finished file."""
    p = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
         "-af", "loudnorm=print_format=json", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    tail = p.stderr[p.stderr.rfind("{"):p.stderr.rfind("}") + 1]
    return json.loads(tail)


def prepare(src, dest, start):
    """Trim, downmix, resample, then loudness-match.

    ORDER MATTERS AND WAS WRONG THE FIRST TIME. Measuring loudness on the source
    and then downmixing to mono afterwards computes the gain for a signal that no
    longer exists by the time it is written. The iPhone tracks are stereo and
    their channels partially cancel when summed, losing 6 to 10 dB, so every
    phone reference went out far below target while the mono studio files landed
    exactly on it.

    Now: cut, downmix, and resample first, then measure THAT, then apply gain.
    The result is verified by the caller rather than assumed.
    """
    stage = dest.with_suffix(".stage.wav")
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-ss", str(start), "-t", str(SECONDS), "-i", str(src),
         "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", str(stage)],
        check=True, capture_output=True,
    )

    m = measure_loudness(stage)
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(stage),
         "-af", (
             f"loudnorm=I={TARGET_LUFS}:TP=-1.5:LRA=11:"
             f"measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
             f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:"
             f"offset={m['target_offset']}:linear=true"
         ),
         "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", str(dest)],
        check=True, capture_output=True,
    )
    stage.unlink()

    verified = float(measure_loudness(dest)["input_i"])
    return float(m["input_i"]), verified


OUT.mkdir(exist_ok=True)
print(f"Window: {SECONDS}s | mono | 48kHz | loudness-matched to {TARGET_LUFS} LUFS (linear)\n")

made = 0
failures = []
for sp in cases["speakers"]:
    start = sp.get("window_start")
    if start is None:
        print(f"{sp['label']}: skipped, no recording yet")
        continue
    for cap, fname in sp["files"].items():
        if not fname:
            continue
        src = REFS / fname
        if not src.exists():
            print(f"  MISSING: {src.name}")
            continue
        dest = OUT / f"{sp['id']}-{cap}.wav"
        before, verified = prepare(src, dest, start)
        ok = "OK " if abs(verified - TARGET_LUFS) < 0.5 else "OFF"
        if ok == "OFF":
            failures.append(dest.name)
        print(f"  {ok} {dest.name:22} <- {fname:26} [{start:.1f}s-{start + SECONDS:.1f}s]  "
              f"{before:7.2f} -> {verified:7.2f} LUFS")
        made += 1

print(f"\n{made} references written to refs_prepared/")
if failures:
    print(f"FAILED to hit {TARGET_LUFS} LUFS: {', '.join(failures)}")
else:
    print(f"All verified within 0.5 LU of {TARGET_LUFS} LUFS after processing.")
    print("Identical length, channel count, sample rate, and measured loudness.")
