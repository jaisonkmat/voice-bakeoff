# Voice Bake-Off

Testing whether Fish Audio's accent-preservation claim holds up.

## The claim being tested

Fish Audio says competing text-to-speech models produce "flattened prosody, neutralized vowels, and a distinct loss of accent identity in cloned voices," and that their model "preserves the accent identity of the source voice rather than normalizing toward an American English baseline."

That is specific and testable. This repo tests it.

## Method

Three speakers, each recorded for roughly 30 seconds of unscripted speech. Each recording is used as the cloning reference for Fish Audio, ElevenLabs, and Cartesia. Every resulting clone reads the same sentence:

> "Last November the weather was very cold, so we waited by the water instead of walking over to the vegetable market."

That sentence is built around the sounds where Indian English and American English diverge: the v/w contrast, the retroflex t, syllable timing, and pure vowels against diphthongs. No speaker ever says it, so it measures generalization rather than playback.

One speaker is an American English control. Each speaker is captured twice on the same take, once through a studio mic and once on a phone, so recording quality is isolated as its own variable.

Full method, controls, and stated limitations are on the published page.

## Layout

```
cases.json              the manifest: speakers, captures, providers, test sentence
refs/                   raw full-length recordings (gitignored, never published)
run.py                  the harness
results.json            raw timings, character counts, and costs
docs/index.html         the published page
docs/audio/reference/   short trimmed clips of each original voice
docs/audio/fish/        generated audio
docs/audio/elevenlabs/
docs/audio/cartesia/
```

Generated audio lives under `docs/` and is committed, because the published page has to be able to play it. The full-length reference recordings are not committed; only short trimmed clips are, which is enough to judge the comparison without publishing several minutes of someone's family talking.

## Reproduce this

You need API keys for all three providers in a `.env` file:

```
FISH_API_KEY=...
ELEVENLABS_API_KEY=...
CARTESIA_API_KEY=...
```

Then:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install fish-audio-sdk python-dotenv httpx
python run.py
```

Swap your own recordings into `refs/` and rerun.

## Note for anyone starting with Fish Audio

Their published Python quickstart says `pip install fishaudio`. That is the wrong package: it installs their open-source model training code, which needs a GPU and is unrelated to the API. The correct package is `fish-audio-sdk`.

Also, API credit is billed separately from platform credit. A new key returns `402 Payment Required` on every model until you top up.

## Consent

Every voice here was recorded by its owner, for this project, with permission. No scraped audio, no film clips, no public figures.
