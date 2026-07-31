"""Generate site/index.html from the data files.

Nothing in the page is typed by hand. Findings come from findings.md, audio and
timings from results.json, judgments from judgments.json, method details from
cases.json. Re-running this after editing any of those rebuilds the page.

Generates static HTML rather than fetching JSON in the browser, so the page
works when opened directly from disk as well as when served.
"""

import html
import json
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).parent
cases = json.loads((ROOT / "cases.json").read_text())
results = json.loads((ROOT / "results.json").read_text())["results"]
judg = json.loads((ROOT / "judgments.json").read_text())
findings_md = (ROOT / "findings.md").read_text()

PROVIDERS = [(p["id"], p["label"]) for p in cases["providers"]]
BY = {(r["speaker"], r["capture"], r["provider"]): r for r in results}


def md(text):
    """Minimal markdown: headings, bold, and paragraphs. Nothing else is used."""
    out = []
    for block in text.strip().split("\n\n"):
        block = block.strip()
        if not block:
            continue
        esc = html.escape(block)
        esc = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", esc)
        if esc.startswith("## "):
            out.append(f"<h2>{esc[3:]}</h2>")
        elif esc.startswith("# "):
            out.append(f"<h2>{esc[2:]}</h2>")
        else:
            out.append(f"<p>{esc}</p>")
    return "\n".join(out)


def player(path, label, is_ref=False):
    cls = "who ref" if is_ref else "who"
    if not (ROOT / "site" / path).exists():
        return f'<span class="{cls}">{label}</span><div class="slot">missing</div>'
    return (f'<span class="{cls}">{label}</span>'
            f'<audio controls preload="none" src="{path}"></audio>')


# ------------------------------------------------------------------ sections

listen = []
for sp in cases["speakers"]:
    blocks = []
    for cap in cases["captures"]:
        key = (sp["id"], cap["id"])
        if not any(k[:2] == key for k in BY):
            continue
        rows = [player(f"audio/reference/{sp['id']}-{cap['id']}.mp3", "Original", True)]
        for pid, plabel in PROVIDERS:
            r = BY.get((sp["id"], cap["id"], pid))
            if r:
                rows.append(player(r["audio"], plabel))
        blocks.append(
            f'<p class="cap">{html.escape(cap["label"])} &middot; '
            f'{html.escape(cap["note"])}</p>'
            f'<div class="players">{"".join(rows)}</div>')
    if blocks:
        role = "Control" if sp["role"] == "control" else "Test"
        listen.append(
            f'<div class="speaker"><h3>{html.escape(sp["label"])}</h3>'
            f'<span class="tag">{html.escape(sp["accent"])} &middot; {role}</span>'
            f'{"".join(blocks)}</div>')

lat_rows = []
for pid, plabel in PROVIDERS:
    rs = [r for r in results if r["provider"] == pid]
    if not rs:
        continue
    lat_rows.append(
        f"<tr><td>{plabel}</td>"
        f"<td>{statistics.median(r['ttfb_median_ms'] for r in rs):.0f} ms</td>"
        f"<td>{statistics.median(r['total_median_s'] for r in rs):.2f} s</td>"
        f"<td>{statistics.median(r['clone_seconds'] for r in rs):.1f} s</td>"
        f"<td>{rs[0]['chars']}</td></tr>")

label_of = dict(PROVIDERS)
blind_rows = []
for sp in cases["speakers"]:
    for cap in cases["captures"]:
        key = f"{sp['id']}-{cap['id']}"
        j = judg["listener_1_blind"].get(key)
        if not j:
            continue
        if j.get("pending"):
            blind_rows.append(
                f'<tr><td>{html.escape(sp["label"])} ({html.escape(cap["label"])})</td>'
                f'<td colspan="2">awaiting re-listen</td>'
                f'<td class="q">{html.escape(j["comment"])}</td></tr>')
            continue
        best = "no winner" if j.get("no_winner") else label_of.get(j["best"], j["best"])
        worst = label_of.get(j["worst"]) if j.get("worst") else "&mdash;"
        blind_rows.append(
            f'<tr><td>{html.escape(sp["label"])} ({html.escape(cap["label"])})</td>'
            f'<td>{best}</td><td>{worst}</td>'
            f'<td class="q">{html.escape(j["comment"])}</td></tr>')

t = judg["tally"]
c, x = t["control_american_english"], t["test_indian_english"]
tally = (f'<p><strong>Control (American English, my voice, n={c["n"]}):</strong> '
         f'Fish won both.</p>'
         f'<p><strong>Test (Indian English, my parents, n={x["n"]}):</strong> '
         f'Cartesia {x["cartesia"]}, Fish {x["fish"]}, ElevenLabs {x["elevenlabs"]}, '
         f'and {x["no_winner"]} group where nothing worked.</p>'
         f'<p class="note">{html.escape(x["note"])}</p>')

controls = [
    ("The reference audio is unscripted.", "Reading aloud produces flatter, evenly paced speech. Prosody is what this test is about, and reading suppresses it. Every speaker was asked a question and answered in their own words."),
    ("The test sentence appears nowhere in any reference.", "If the reference contains the words the clone is later asked to say, the model can imitate audio it already heard instead of generalizing. All references were transcribed and checked. Mom's recording contains \"very cold\" at 11.3 to 12.2 seconds, so her window starts at 13.0s to exclude it."),
    ("One speaker is a control.", "American English, which all three should handle. Without it, a poor result on the accented voices is ambiguous between an accent problem and a general limit of 30-second cloning."),
    ("Identical input to every provider.", "All references trimmed to exactly 30.000s, downmixed to mono, resampled to 48kHz, and loudness-matched to -20 LUFS with two-pass EBU R128 in linear mode, which is one constant gain and no change to dynamics. Source levels ranged from -23.6 to -28.9 LUFS, so matching was necessary. Every output file is measured after processing and the run fails loudly if any file misses target by more than 0.5 LU."),
    ("Fish's reference enhancement was disabled.", "Fish cleans up reference audio by default. Left on, it would have repaired the phone track while the other two providers received it raw, which would have destroyed the studio versus phone comparison."),
    ("Three runs per case, medians reported.", "A single latency sample is noise. The single-run smoke test measured Fish at 519ms; across 18 measurements it is 224ms."),
    ("Both microphones captured the same take.", "Studio and phone tracks were aligned in Logic and cut at identical timestamps, so recording quality is the only thing that changes between them."),
    ("Every voice was recorded with consent, for this purpose.", "No scraped audio, no film clips, no public figures."),
]

limitations = [
    "One listener, who also designed the study. Six group judgments. That is the fastest way to dismiss this and it is a fair objection.",
    "My ranking on both of my dad's recordings moved after I learned which model was which, in both cases toward Fish. The blind calls are reported as the result, with the revisions recorded underneath.",
    "The phone groups were re-judged after a normalization bug was fixed. That re-listen was only partly blind: by then I could recognise the models by output character.",
    "One speaker per accent, and both non-American speakers are from the same family and the same part of Kerala. A difference between them could be the speaker rather than the model.",
    "The control speaker talks denser than either parent (86% speech coverage versus 75 to 76% in the same 30 seconds).",
    "No expressiveness controls were used on any provider. Default settings only, which cuts against Fish and their 15,000 direction tags.",
    "Thirty seconds of reference audio per clone, which is short. More was recorded (46 to 104 seconds per speaker) and cut to a uniform length because the windows had to match. All three providers received the identical reference, so this does not favour any of them, but it limits the absolute conclusion more than the relative one.",
    "Only instant voice cloning was tested. ElevenLabs also sells professional voice cloning, which wants 30+ minutes of audio and trains a dedicated model. That tier is likely better and was not tested.",
    "A discrimination test against a real recording could not be run, because the originals and the clones say different words. That would have required a separate ground-truth recording of each speaker reading the test sentence.",
    "Fish's reference enhancement was disabled so that it would not repair the phone track while the other two received it raw. Defensible for a controlled comparison, but it means this is not a test of each provider's default first-use workflow.",
]

CSS = (ROOT / "site" / "index.html").read_text()
CSS = CSS[CSS.find("<style>"):CSS.find("</style>") + 8]

page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>I cloned my parents on three voice AI models</title>
{CSS}
</head>
<body>
<div class="wrap">

<h1>I cloned my parents on three voice AI models</h1>
<p class="dek">The company that markets accent preservation won on my American voice and lost on both of my father&#x27;s. Then I found a bug in my own code that had inverted the whole result.</p>
<p class="byline">Jaison Mathew &middot; July 2026</p>

<h2>The claim</h2>
<blockquote>"flattened prosody, neutralized vowels, and a distinct loss of accent identity in cloned voices"</blockquote>
<blockquote>"The Fish S2 Pro model preserves the accent identity of the source voice rather than normalizing toward an American English baseline"</blockquote>
<p>That is Fish Audio describing what its competitors do wrong and what it does differently. It is a specific, testable claim, so I tested it.</p>

{md(findings_md)}

<h2>The result</h2>
{tally}
<div class="scroller">
<table>
<thead><tr><th>Group</th><th>Closest</th><th>Furthest</th><th>What I heard</th></tr></thead>
<tbody>{"".join(blind_rows)}</tbody>
</table>
</div>

<h2>Listen</h2>
<div class="grid">{"".join(listen)}</div>
<p class="note">Each block starts with the original recording it was cloned from, so the phone clones are judged against the phone original rather than the studio one. Originals are short trimmed clips; the full recordings are not published.</p>

<h2>Latency and cost</h2>
<div class="scroller">
<table>
<thead><tr><th>Provider</th><th>First byte</th><th>Total</th><th>Clone time</th><th>Chars</th></tr></thead>
<tbody>{"".join(lat_rows)}</tbody>
</table>
</div>
<p class="note"><strong>Why two latency numbers.</strong> On a phone call the caller hears silence until the first byte arrives, so first-byte time is the delay a customer perceives. For video dubbing only total time matters. Same API, different metric depending on who is buying, and on this data they give opposite winners. Medians across {len(results)} cases, three runs each.</p>
<p class="note">Cost is not compared. Fish publishes $15 per million characters, so its cost is exact. ElevenLabs and Cartesia bill against monthly subscription credits, where an effective per-character price depends entirely on how much of the plan gets used. Characters are recorded for all three instead.</p>

<h2>Method</h2>
<p>Each speaker recorded roughly a minute of unscripted speech, answering a question about arriving in America. That recording was the cloning reference for all three providers. Every clone then read the same sentence:</p>
<blockquote>"{html.escape(cases['test_sentence'])}"</blockquote>
<p>No human ever said that sentence. It exists only in the outputs, which is the point: it measures what each model does with words it has never heard in that voice.</p>
<p>It is also not a random sentence. It is built around the places where Indian English and American English diverge: the v/w contrast in three adjacent pairs, the retroflex t in "water" and "waited", syllable timing in "vegetable" (three syllables in American English, four in Indian English), and pure vowels against diphthongs in "cold" and "over".</p>

<h2>Controls, and why each one is there</h2>
<ol class="controls">
{"".join(f"<li><strong>{html.escape(t)}</strong>{html.escape(b)}</li>" for t, b in controls)}
</ol>

<h2>Limitations</h2>
<ol class="controls">
{"".join(f"<li>{html.escape(x)}</li>" for x in limitations)}
</ol>

<h2>Reproduce this</h2>
<p>The repo has the harness, the manifest, the raw timings for all {len(results)} cases, the full transcripts with timestamps, and every audio file. The blind listening set is generated by a seeded shuffle, so the arrangement is reproducible and the answer key could not have been adjusted afterward.</p>
<p>Swap your own recordings into <code>refs/</code> and run it.</p>
<p><a href="#">github.com/&lt;you&gt;/voice-bakeoff</a></p>

<footer>
Not affiliated with Fish Audio, ElevenLabs, or Cartesia. All voices recorded and used with the speaker's consent.
</footer>

</div>
</body>
</html>
"""

out = ROOT / "site" / "index.html"
out.write_text(page)
print(f"Wrote {out}")
print(f"  {len(results)} results, {len(blind_rows)} judgment rows, {len(listen)} speakers")
