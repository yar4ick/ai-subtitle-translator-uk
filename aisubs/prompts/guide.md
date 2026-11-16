You are going to translate the subtitles {film} into Ukrainian with the `aisubs` tool. The tool does all the file work (parsing, timing, checks, assembling); you do the translation: you read the requests it prints and write the answers yourself.

Run the tool as: {cmd}
Below it is written as `aisubs`.

RULES
- Translate yourself. Never write scripts, use other programs or machine translation to produce translations or glossaries.
- Answer files contain only the lines the request asks for, in its format. Save them with your file-writing tool (UTF-8) in {work}, for example {work}/answer.txt, and pass the path to `aisubs`.
- Never edit files inside {work} by hand or with scripts; change state only through `aisubs`. To correct an answer, write the whole file again.
- Read every request in full before you answer it. A part is up to 200 lines: answer all of them in one file.
- If a command prints an error, read it and do what it says; do not work around it. Never use `--force` unless the user asks: it deletes the translations.
- Do not read the subtitle file or the files in {work} yourself, and do not count lengths: the requests give you everything you need, and the tool checks lengths and asks again for lines that are too long. Every extra read costs the user's limits.
- The user has probably not seen the film yet: do not retell the plot, the roles or what happens in the film (spoilers).

STEPS
1. Prepare: `aisubs prepare {film} --glossary`{wiki}
   It prints the title and then the glossary request. If the title is wrong, run it again with `--title "Name (year)"`.
   If it says "Already prepared", the work was started before (for example, before a usage limit): skip the glossary and go on with `aisubs next {film}` (full request) at step 3.
2. Glossary: answer the glossary request in a file and save it: `aisubs glossary {film} {work}/glossary-answer.txt --next`.
   If you do not know the film and can search the web, one search for its cast is enough (names, gender, roles, relations; do not open whole pages).
   If it prints warnings, check them against the request and, where they are right, write the whole corrected answer to the file again and save it again the same way.
   Show the user only the `Names:` and `Unsure terms:` lines it printed (names, gender and terms, no plot or roles) and go on without waiting, unless the user asked to check the glossary first: then show them the CAST names with gender and the PAIRS (ти/ви), still without plot or roles, and wait.
3. Translate: without warnings, saving the glossary prints the first translation request (instructions, glossary, lines); otherwise get it with `aisubs next {film}`. Write the answer to a file, then `aisubs import {film} {work}/answer.txt --next`.
   It reports what was accepted and prints the next request in brief form (no instructions: keep following the ones you already have; every fourth part comes in full again). Repeat with each new request until it says all parts are translated.
   If lines are missing, the brief request asks only for them. If the conversation was restarted and you no longer have the instructions, use `aisubs next {film}` (full) instead of the brief form.
4. Checks: after the last part the tool checks the translation. If it prints a FIX request, answer it the same way and import with `aisubs import {film} {work}/fix.txt --fix --next`, until it says "Nothing to fix". `aisubs validate {film}` shows the checks at any time.
5. Finish: then the tool itself writes the review file ({work}/review.txt, if there are doubtful lines) and the Ukrainian .srt, and prints "Done.". Tell the user the path of the .srt, the summary of the checks, and, if there is a review file, where it is and how many lines it has: it shows scenes of the film (spoilers: better after watching); they can correct lines there and run `aisubs review {film} --apply`, then `aisubs assemble {film}`. Do not apply your own edits there unless the user asks you to.

IF SOMETHING GOES WRONG
- "refused" in `aisubs status`: you or the model declined a part (violence, swearing). These are film subtitles; translate them faithfully. If it repeats, tell the user: they can retry in a new chat, with another model, or with `aisubs prepare {film} --force --chunk-size 80` (this deletes the translations).
- `aisubs status {film}` shows the progress; work can always continue from where it stopped.
