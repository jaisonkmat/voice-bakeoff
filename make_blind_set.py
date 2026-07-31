"""Build a blind listening set.

Providers are shuffled independently within each speaker/capture group, so the
A/B/C mapping cannot be learned from one group and applied to the next.

The shuffle is seeded, which means it is reproducible: anyone re-running this
gets the identical arrangement and can verify the answer key was not adjusted
after the fact.

Speaker and capture stay visible. The listener has to know whose voice it is to
judge it, and phone audio is audibly thinner anyway, so hiding it would achieve
nothing.
"""

import json
import random
import shutil
from pathlib import Path

ROOT = Path(__file__).parent
AUDIO = ROOT / "docs" / "audio"
BLIND = ROOT / "listen"
SEED = 20260730

cases = json.loads((ROOT / "cases.json").read_text())
random.seed(SEED)

if BLIND.exists():
    shutil.rmtree(BLIND)
BLIND.mkdir()

key = {}
sheet = ["# Blind listening sheet",
         "",
         f'Test sentence: "{cases["test_sentence"]}"',
         "",
         "Listen to ORIGINAL first, then A, B, C. For each group write which letter",
         "sounds most like the person and which sounds least like them.",
         "",
         "What to listen for, in order:",
         "  1. water / waited    hard t, or soft American d?",
         "  2. weather was very  are w and v distinct, or the same sound?",
         "  3. vegetable         three syllables or four?",
         "  4. cold / over       gliding vowel, or pure?",
         "  5. rhythm            even syllables, or English stress-and-mumble?",
         ""]

order = 0
for sp in cases["speakers"]:
    for cap in cases["captures"]:
        group = f"{sp['id']}-{cap['id']}"
        src_ref = AUDIO / "reference" / f"{group}.mp3"
        if not src_ref.exists():
            continue
        order += 1
        folder = BLIND / f"{order} - {sp['label']} ({cap['label']})"
        folder.mkdir()
        shutil.copy(src_ref, folder / "ORIGINAL.mp3")

        providers = [p["id"] for p in cases["providers"]]
        random.shuffle(providers)
        for letter, prov in zip("ABC", providers):
            src = AUDIO / prov / f"{group}.mp3"
            if src.exists():
                shutil.copy(src, folder / f"{letter}.mp3")
                key[f"{folder.name}/{letter}"] = prov

        sheet += [f"## {order}. {sp['label']} ({cap['label']}) - {sp['accent']}",
                  "", "  most like them:  ____", "  least like them: ____",
                  "  notes:", "", ""]

(BLIND / "SCORING SHEET.md").write_text("\n".join(sheet))
(ROOT / ".scratch" / "answer_key.json").write_text(
    json.dumps({"seed": SEED, "key": key}, indent=2))

print(f"{order} groups written to listen/")
print(f"Answer key hidden in .scratch/answer_key.json (seed {SEED})")
print("\nFolders:")
for f in sorted(BLIND.iterdir()):
    if f.is_dir():
        print(f"  {f.name}")
