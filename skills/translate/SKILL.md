---
name: translate
description: Translate SRT subtitles (a film or an episode) from English into Ukrainian with the aisubs tool, which handles parsing, glossary, checks and assembling. Use when the user asks to translate subtitles or an .srt file into Ukrainian.
argument-hint: "<film.srt> [wishes, e.g. --wikipedia, check the glossary with me first]"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/aisubs *), Bash(python ${CLAUDE_PLUGIN_ROOT}/aisubs *)
---

Translate subtitles into Ukrainian. The user's request: $ARGUMENTS

1. Find the .srt file the user means (ask if none is given or it does not exist). Put the path in quotes if it has spaces.
2. Run `python3 ${CLAUDE_PLUGIN_ROOT}/aisubs guide <film.srt> --command "python3 ${CLAUDE_PLUGIN_ROOT}/aisubs"`.
   If `python3` is not found (Windows), use `python` in both places. Python 3.10 or newer is needed; nothing has to be installed.
3. Follow the printed instructions to the end, in this conversation. One difference: here, do not save answers to files. Pass each answer to the tool on stdin with a heredoc, in the same command; these commands are pre-approved, so the user is not asked each time:
   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/aisubs import <film.srt> - --next <<'AISUBS_END'
   …the answer lines…
   AISUBS_END
   ```
   The same for the glossary (`aisubs glossary <film.srt> - <<'AISUBS_END'`) and for fixes (`aisubs import <film.srt> - --fix --next <<'AISUBS_END'`). To correct an answer, send the whole corrected answer again the same way.
   Run every `aisubs` command on its own, starting with `python3 ${CLAUDE_PLUGIN_ROOT}/aisubs`: no `mkdir`, shell variables, `;` or `&&` around it, or the user is asked for permission. The tool creates its folders itself.
   Take into account the user's wishes from the request above (for example `--wikipedia`, or to stop and check the glossary with them first).
4. At the end, tell the user in their language where the translated .srt and the review file are, and summarise the checks.
