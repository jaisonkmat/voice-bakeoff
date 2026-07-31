# What I found

Fish Audio says competing models flatten non-American accents while theirs preserve them. I have two parents who came here from Kerala in the 1980s, so I tested it.

I cloned three voices on Fish, ElevenLabs, and Cartesia. My mom, my dad, and me as a control, since I was born in New York and don't have their accent. Everyone recorded about a minute of unscripted speech on a studio mic and an iPhone at the same time. Then every clone read the same sentence, one nobody had said, built around the sounds where Indian English and American English split. I listened to all eighteen outputs blind and revealed which was which afterward.

Fish won both control tests on my own voice, and one of the four on my parents. Cartesia took two. On my mom's phone recording nothing worked at all.

That is not the result I expected, and it is not the result I had a few hours ago. I'll get to why.

The tally matters less than this: none of them sounded like my parents. I said some version of "it's not even that good" on every group. The clone of my own voice would have fooled my mother on a voicemail. Same pipeline, same thirty seconds of reference. It cleared the bar on me and on neither of them.

## Models overshoot accents, and nobody markets against it

Fish's public claim is about one kind of failure: flattened prosody, neutralized vowels, accents collapsing toward American. Undershoot.

I heard the opposite failure twice, from two different companies, on the same speaker.

On my dad's studio recording, Cartesia pushed his accent past where he actually takes it, more emphatic and more generic than how he speaks. It said "walking" as "WOKing." The phonetic term is articulatory overshoot: the articulators travel past their target and every sound comes out over-precise. It had learned the category and not the person. Some words were fine, "so we" sounded like him, then "water" would arrive doing far too much and break it.

On his phone recording, Fish did the same thing on the same word. Too much weight on "water," trying the accent too hard.

So this isn't one company's bug. On a voice with a strong accent, models overshoot, and the industry only has language for the opposite problem.

Worth separating two things that fail independently. Cartesia got roughly who my dad was and then performed his accent wrong. Fish, on his studio recording, sounded like a different person entirely. Accent and identity are separate failures with separate fixes, and casual comparisons collapse them.

One more thing about "WOKing." I ran all three outputs through speech recognition and every one transcribed "walking" correctly. The distortion is obvious to a human ear and not big enough to break a machine. That makes it a naturalness problem, not an intelligibility one.

## The clone stops being the person mid-sentence

On my mom's phone version, the beginning sounded like her, and by the last word, "market," it was somebody else. Seven seconds.

I heard the same shape on my dad. Fine at the start, drifting into caricature by the end.

## Why the result changed

I asked a model to attack this study before I published it. Its criticism was that I asserted my loudness normalization worked without ever measuring the output.

I measured. It had failed on every stereo file, by up to 10.7 dB.

I was measuring loudness on the source and then downmixing to mono afterward, so the gain was computed for a signal that no longer existed by the time it was written. The iPhone tracks are stereo and their channels partially cancel when summed. Every phone reference went to all three providers far quieter than intended. The mono studio files were fine, which is why the bug was invisible.

I fixed the order, made the script verify every output and fail loudly if it misses, regenerated the phone half, and listened again.

**The conclusion inverted.** Before the fix, Fish won three of four on Indian English. After it, Cartesia leads two to one. My original result was substantially an artifact of my own bug.

That is the most useful thing in here. If I had sent it four hours ago I would have sent the wrong answer, confidently, with the audio to back it up.

## What I'm not claiming

I am one person who judged six groups. That is the fastest way to dismiss this and it is a fair objection. There is no fix for it except more listeners.

My ranking on my dad's recordings moved after I learned which model was which, in both cases toward Fish. The blind calls are what I'm reporting, with the revisions recorded underneath, because the blind ones are the data and the revisions are what my ears did once they knew the answer.

The phone re-listen was only partly blind. By then I could recognize these models by character.

This is a case study, not a result. A proper version needs twenty-odd listeners with no connection to the speakers and dozens of voices per accent. Everything here is published so someone can run that version. What I'm claiming is that I heard something specific and repeatable, not that I've measured it.

## What this doesn't test

Every provider got the same 115 characters of plain text with default settings. No emotion tags, no SSML, no Fish direction tags, no Cartesia controls, no ElevenLabs voice settings. Adding markup to one and not the others would compare my prompting rather than their models. That cuts against Fish, who advertise 15,000 direction tags I never touched.

Every clone was built from thirty seconds of reference. That is short. I recorded more, between 46 and 104 seconds per person, and cut everyone to the same length because the windows had to match. All three providers got the identical thirty seconds, so it doesn't favour any of them, but "none of them sounded like my parents" might not survive three minutes of reference instead of thirty seconds.

I also only tested instant cloning. ElevenLabs sells professional voice cloning that wants thirty minutes or more and trains a dedicated model. That is probably better and I didn't touch it.
