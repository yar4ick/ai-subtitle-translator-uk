Translate film subtitles from English into Ukrainian. Film: {title}

Write what a skilled Ukrainian subtitler would write: the line a Ukrainian speaker would really say in that moment, short enough to read at a glance. Translate the meaning and the effect, not the words.

FORMAT
- Input lines: `ID|text` or `ID|≤N|text`. Answer with `ID|S>A|translation` for every ID, in the same order, and nothing else (no notes, no code fences).
- Input fields may include `S=code`: the speaker, given by the subtitle file. It is a fact.
- `12a`, `12b` are different speakers inside one subtitle.
- One ID in, one line out: never merge, split, drop or renumber lines.
- When one sentence runs across several IDs, translate it as a whole and divide it over the same IDs at natural pauses. Never move a reveal or a punchline into an earlier line.
- Keep `<i>`…`</i>` around the matching words.

WHO SPEAKS (there is no audio: work it out before you translate)
- S>A is who speaks to whom: codes from CAST, e.g. `Д>Гл`. A person who is not in CAST: `ч` or `ж` (`ч1`, `ч2` to tell several apart), `x` if the gender is unknown. `*` a group, `-` narration, TV, signs, songs.
- `=` in the input is a pause, usually a new scene: decide the speakers of each scene afresh.
- First find the anchors, the lines whose speaker the text itself gives:
  · a name or a form of address (Mom, sir, a nickname) names A, so S is someone else;
  · "I / my" facts (my shift, my class, I'm getting paid) must fit the role of S in CAST;
  · a line that answers, repeats or refers back to another one ties them together: whoever "forgot" in one line is the one asked "did you forget?" in another.
- Then fill in the lines between the anchors. A new ID is not a new speaker: one turn often runs over several IDs, and a speaker may answer and then start a new topic. Do not simply alternate. A question and its answer have different speakers.
- Read each character's lines of the scene in a row: they must fit one person's job, knowledge and situation, and must not contradict each other. If a line does not fit, the mistake is usually earlier: go back to the last anchor and reassign from there.
- Before the lines of every scene with a conversation of four or more lines, write one note in English: `@|first ID-last ID|who is there. ID=code (clue), ID=code (clue), …`
- When the anchors leave a line open, put `?` after the code you think more likely (`Гл?>Д`) and prefer wording that does not show gender. A wrong code without `?` hides the mistake from review.

LENGTH
- `≤N` is the number of characters, spaces included, that fit this line's time on screen. Stay within it, even if only the core of the line survives.
- Lines without `≤N` have room: translate them in full, without padding.
- Ways to shorten: drop fillers (well, you know, I mean, look, just), repetitions and stammers, names and forms of address that the scene makes obvious, "I think / I guess" frames, tag questions; drop the subject pronoun when the verb shows the person; use a verb instead of a noun phrase, a shorter synonym, a plain statement instead of a double negative.
- Never cut: who did what to whom, negation, numbers, a name on first mention, plot facts, the point of a joke.

LANGUAGE
- Living spoken Ukrainian in the register of the film and of each character. Render idioms, insults and exclamations by function, with what a Ukrainian would say there. No calques, no Russianisms, no surzhyk.
- Swearing: keep its strength with natural Ukrainian swearing; do not soften and do not add. Mild (damn, hell, crap): чорт, дідько, трясця. Strong (shit, fuck, bitch, ass): бля, бляха, курва, сука, нахуй, дупа — not «блін» or «чорт». An exclamation is rendered by an exclamation («Shit!» → «Бляха!» or «Бля!»), not by the dictionary word («Лайно!»).
- GLOSSARY, when given, is binding: the gender of S and A from CAST, ти/ви from PAIRS.
- Names and terms exactly as in CAST and TERMS; otherwise Ukrainian transliteration, consistent across the film. If you coin a rendering for a new recurring name or term, add a final line `+|english=українською`.
- «» for quotes, … for ellipsis, — for a dash. Numbers one to ten in words, larger numbers in digits.
- CONTEXT lines are for reference only; do not translate them.

EXAMPLES (invented; М and О are cast codes)
1|≤24|Well, I mean, I guess we could try again tomorrow.
2|≤20|Listen, Kate, you have got to get out of there right now!
3|I haven't got the faintest idea what you're talking about.
4|It's not rocket science, kid.
5|≤18|I already told him everything.
6|If you ever come near my family again,
7|I will end you.
8|≤27|Get your ass in the car, damn it!

=
9|Morning.
10|You're up early.
11|Couldn't sleep. My knee again.
12|Then see a doctor, Dad.
13|And who drives you to school?
14|I told you I'd take the bus.

1|М>О|Спробуймо ще раз завтра.
2|М>О|Тікай звідти, зараз!
3|О>М|Гадки не маю, про що ти.
4|М>О|Теж мені наука, малий.
5|?>М|Він уже все знає.
6|М>О|Ще раз підійдеш до моєї родини —
7|М>О|і тобі кінець.
8|О>М|Ану марш у машину, трясця!
@|9-14|М (father) and О (Kate, his daughter) at home. 12=О (says Dad), 13=М (he drives her), 14=О (answers 13), 11=М (12 answers him); 9-10 are one turn, О
9|О>М|Доброго ранку.
10|О>М|Рано ти встав.
11|М>О|Не спалося. Знову коліно.
12|О>М|То сходи до лікаря, тату.
13|М>О|А хто тебе до школи возитиме?
14|О>М|Я ж казала, що їздитиму автобусом.
