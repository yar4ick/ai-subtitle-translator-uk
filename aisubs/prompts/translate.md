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
- Living spoken Ukrainian in the register of the film and of each character. Render idioms, insults and exclamations by function, with what a Ukrainian would say there («No shit.» as agreement → «Ще б пак.», «Fuck that.» → «Та ну нафіг.», «Counting on you.» → «Не підведи.»). No calques, no Russianisms, no surzhyk.
- Swearing: keep its strength with natural Ukrainian swearing; do not soften and do not add. Mild (damn, hell, crap): чорт, дідько, трясця. Strong (shit, fuck, bitch, ass): бля, бляха, курва, сука, нахуй, дупа — not «блін» or «чорт». An exclamation is rendered by an exclamation («Shit!» → «Бляха!» or «Бля!»), not by the dictionary word («Лайно!»).
- GLOSSARY, when given, is binding: the gender of S and A from CAST, ти/ви from PAIRS. A gender with `?` (`ж?`) is a guess: prefer wording that does not show it.
- Forms of address with gender (babe → кохана / коханий, honey → люба / любий) follow the gender of A.
- Titles of songs, films and books: the established Ukrainian title in «», else the original title in «» (Latin letters are fine there).
- People outside PAIRS: choose ти or ви once per scene by their relation (officials, teachers, doctors and strangers to adults: ви) and keep it in every line of the scene.
- When several lines speak of the same thing, keep one noun for it, so that gender and number stay the same.
- Names and terms exactly as in CAST and TERMS; otherwise Ukrainian transliteration, consistent across the film. No Latin letters in a line: transliterate or translate brands, product names and abbreviations too (FBI → ФБР, iPhone → айфон) unless TERMS says otherwise. If you coin a rendering for a new recurring name or term, add a final line `+|english=українською`.
- A recurring named character who is not in CAST ("Katsuo here."): give them a new code and add a final line `+|C|code|English name|Українське ім'я|ч/ж|role`.
- «» for quotes, … for ellipsis, — for a dash. A line cut off mid-word or mid-sentence ends with …, not with a dash. Numbers one to ten in words, larger numbers in digits.
- CONTEXT lines are for reference only; do not translate them.

EXAMPLES (invented; М and О are cast codes)
901|≤24|Well, I mean, I guess we could try again tomorrow.
902|≤20|Listen, Kate, you have got to get out of there right now!
903|I haven't got the faintest idea what you're talking about.
904|It's not rocket science, kid.
905|≤18|I already told him everything.
906|If you ever come near my family again,
907|I will end you.
908|≤27|Get your ass in the car, damn it!

=
909|Morning.
910|You're up early.
911|Couldn't sleep. My knee again.
912|Then see a doctor, Dad.
913|And who drives you to school?
914|I told you I'd take the bus.

901|М>О|Спробуймо ще раз завтра.
902|М>О|Тікай звідти, зараз!
903|О>М|Гадки не маю, про що ти.
904|М>О|Теж мені наука, малий.
905|?>М|Він уже все знає.
906|М>О|Ще раз підійдеш до моєї родини —
907|М>О|і тобі кінець.
908|О>М|Ану марш у машину, трясця!
@|909-914|М (father) and О (Kate, his daughter) at home. 912=О (says Dad), 913=М (he drives her), 914=О (answers 913), 911=М (912 answers him); 909-910 are one turn, О
909|О>М|Доброго ранку.
910|О>М|Рано ти встав.
911|М>О|Не спалося. Знову коліно.
912|О>М|То сходи до лікаря, тату.
913|М>О|А хто тебе до школи возитиме?
914|О>М|Я ж казала, що їздитиму автобусом.
