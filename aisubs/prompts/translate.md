Translate film subtitles from English into Ukrainian. Film: {title}

Write what a skilled Ukrainian subtitler would write: the line a Ukrainian speaker would really say in that moment, short enough to read at a glance. Translate the meaning and the effect, not the words.

FORMAT
- Input lines: `ID|text` or `ID|≤N|text`. Answer with `ID|translation` for every ID, in the same order, and nothing else (no notes, no code fences).
- `12a`, `12b` are different speakers inside one subtitle.
- One ID in, one line out: never merge, split, drop or renumber lines.
- When one sentence runs across several IDs, translate it as a whole and divide it over the same IDs at natural pauses. Never move a reveal or a punchline into an earlier line.
- Keep `<i>`…`</i>` around the matching words.
- If gender or number of the speaker or the addressee, or ти/ви, is unclear from context, add `?` after the ID: `12?|…`.

LENGTH
- `≤N` is the number of characters, spaces included, that fit this line's time on screen. Stay within it, even if only the core of the line survives.
- Lines without `≤N` have room: translate them in full, without padding.
- Ways to shorten: drop fillers (well, you know, I mean, look, just), repetitions and stammers, names and forms of address that the scene makes obvious, "I think / I guess" frames, tag questions; drop the subject pronoun when the verb shows the person; use a verb instead of a noun phrase, a shorter synonym, a plain statement instead of a double negative.
- Never cut: who did what to whom, negation, numbers, a name on first mention, plot facts, the point of a joke.

LANGUAGE
- Living spoken Ukrainian in the register of the film and of each character. Render idioms, insults and exclamations by function, with what a Ukrainian would say there. No calques, no Russianisms, no surzhyk.
- Swearing: keep its strength with natural Ukrainian swearing; do not soften and do not add.
- GLOSSARY, when given, is binding: use the gender of the speaker and the addressee from CAST and ти/ви from PAIRS; work out who speaks to whom from the scene. When it is still unclear, prefer wording that does not show gender if it sounds natural.
- Names and terms exactly as in CAST and TERMS; otherwise Ukrainian transliteration, consistent across the film. If you coin a rendering for a new recurring name or term, add a final line `+|english=українською`.
- «» for quotes, … for ellipsis, — for a dash. Numbers one to ten in words, larger numbers in digits.
- CONTEXT lines are for reference only; do not translate them.

EXAMPLES (invented)
1|≤24|Well, I mean, I guess we could try again tomorrow.
2|≤20|Listen, Kate, you have got to get out of there right now!
3|I haven't got the faintest idea what you're talking about.
4|It's not rocket science, kid.
5|≤18|I already told him everything.
6|If you ever come near my family again,
7|I will end you.
8|≤27|Get your ass in the car, damn it!

1|Спробуймо ще раз завтра.
2|Тікай звідти, зараз!
3|Гадки не маю, про що ти.
4|Теж мені наука, малий.
5|Він уже все знає.
6|Ще раз підійдеш до моєї родини —
7|і тобі кінець.
8|Ану марш у машину, трясця!
