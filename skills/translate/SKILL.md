---
name: translate
description: Translate SRT subtitles (a film or an episode) from English into Ukrainian with the aisubs tool, which handles parsing, glossary, checks and assembling. Use when the user asks to translate subtitles or an .srt file into Ukrainian.
argument-hint: "<film.srt> [wishes, e.g. --wikipedia, check the glossary with me first]"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/aisubs *), Bash(python ${CLAUDE_PLUGIN_ROOT}/aisubs *), Read, Write
---

Translate subtitles into Ukrainian. The user's request: $ARGUMENTS

1. Find the .srt file the user means (ask if none is given or it does not exist). Put the path in quotes if it has spaces.
2. Run `python3 ${CLAUDE_PLUGIN_ROOT}/aisubs guide <film.srt> --command "python3 ${CLAUDE_PLUGIN_ROOT}/aisubs"`.
   If `python3` is not found (Windows), use `python` in both places. Python 3.10 or newer is needed; nothing has to be installed.
3. Follow the printed instructions to the end, in this conversation. Take into account the user's wishes from the request above (for example `--wikipedia`, or to stop and check the glossary with them first).
4. At the end, tell the user in their language where the translated .srt and the review file are, and summarise the checks.
