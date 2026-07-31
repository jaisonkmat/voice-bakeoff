"""Transcribe the reference recordings and flag overlap with the test sentence.

The test sentence must not appear in the reference audio, or a model can imitate
words it already heard in that voice instead of generalizing to new ones. This
finds the timestamps of any collision so we can pick a clean window.

Calls the Fish ASR endpoint directly rather than through the SDK: the SDK sends
a model header the ASR endpoint rejects, and then crashes trying to parse the
non-JSON error response.
"""

import json
import os
import re
import sys

import httpx
import ormsgpack
from dotenv import load_dotenv

load_dotenv()
KEY = os.environ["FISH_API_KEY"]

cases = json.load(open("cases.json"))
TEST_SENTENCE = cases["test_sentence"]

# Content words only. Articles and filler appear in any English sentence and
# carry no phonetic weight for this test.
STOPWORDS = {"the", "so", "we", "by", "of", "at", "to", "a", "in", "and", "it", "was", "over"}
TARGETS = {w for w in re.findall(r"[a-z]+", TEST_SENTENCE.lower()) if w not in STOPWORDS}


def transcribe(path):
    with open(path, "rb") as f:
        audio = f.read()
    r = httpx.post(
        "https://api.fish.audio/v1/asr",
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/msgpack"},
        # ignore_timestamps defaults to True and silently returns zero segments.
        # Without this the collision check scans nothing and reports "clean".
        content=ormsgpack.packb({"audio": audio, "language": "en", "ignore_timestamps": False}),
        timeout=300,
    )
    r.raise_for_status()
    return r.json()


# Merge into existing transcripts rather than replacing them. Starting from an
# empty dict silently destroys the transcripts of any file not named in argv.
OUTFILE = "transcripts.json"
results = json.load(open(OUTFILE)) if os.path.exists(OUTFILE) else {}

print(f"Test sentence: {TEST_SENTENCE}")
print(f"Watching for: {', '.join(sorted(TARGETS))}\n")

for path in sys.argv[1:]:
    name = os.path.splitext(os.path.basename(path))[0]
    print(f"{'=' * 72}\n{name}\n{'=' * 72}")

    d = transcribe(path)
    segments = d.get("segments") or []

    hits = []
    for seg in segments:
        overlap = set(re.findall(r"[a-z]+", seg["text"].lower())) & TARGETS
        if overlap:
            hits.append({"start": seg["start"], "end": seg["end"],
                         "words": sorted(overlap), "text": seg["text"].strip()})

    results[name] = {"text": d["text"], "segments": segments, "collisions": hits}

    print(f"{len(segments)} segments, {len(hits)} with collisions\n")
    for h in hits:
        print(f"  [{h['start']:6.1f}s - {h['end']:6.1f}s]  {h['words']}")
        print(f"     \"{h['text']}\"\n")
    if not hits:
        print("  Clean. No test-sentence words anywhere.\n")

json.dump(results, open(OUTFILE, "w"), indent=2)
print("Full transcripts written to transcripts.json")
