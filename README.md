# ai-subtitle-translator-uk

**Українською** · [English](#english)

Переклад субтитрів SRT з англійської на українську за допомогою ШІ-агента: Claude Code, Antigravity CLI (Gemini) або будь-якого іншого, що вміє запускати команди. Можна й вручну, через веб-чат.

Перекладає модель, а всю решту робить невеликий інструмент `aisubs` (Python, без залежностей):
- ділить субтитри на частини й сцени, рахує, скільки символів уміщується в кожен рядок за час показу;
- складає глосарій: імена, рід персонажів, хто до кого звертається на «ти» чи «ви», терміни; за бажанням бере акторський склад із Вікіпедії;
- перевіряє переклад: довжину й швидкість читання, рід дієслів відповідно до мовця, імена, неперекладені рядки, російські літери, теги;
- повертає моделі лише рядки з помилками, а сумнівні місця збирає у файл для перегляду людиною;
- збирає готовий `film.uk.srt` з оригінальними таймінгами.

Модель отримує лише текст рядків без таймінгів і відповідає коротким форматом, тож токенів іде мало. 25-хвилинна серія (290 субтитрів) у Claude Code із Sonnet коштує близько $0.5 за цінами API і займає 4–5 хвилин.

## Що потрібно

- Python 3.10 або новіший (нічого встановлювати не треба);
- англійські субтитри `.srt`;
- ШІ-агент або доступ до чату з моделлю.

## Claude Code

Встановіть плагін (один раз):

```
/plugin marketplace add yar4ick/ai-subtitle-translator-uk
/plugin install aisubs@aisubs
```

Перейдіть у папку з субтитрами, запустіть `claude` і напишіть:

```
/aisubs:translate film.srt
```

Після назви файлу можна додати побажання, наприклад:
- `/aisubs:translate film.srt --wikipedia` — взяти акторський склад із Вікіпедії (рекомендовано для відомих фільмів і серіалів);
- `/aisubs:translate film.srt перевір глосарій зі мною` — показати імена, рід і «ти/ви» перед перекладом і дочекатися вашого підтвердження.

Агент пройде всі кроки сам і не питатиме дозволів: виклики `aisubs` плагін дозволяє наперед. Рекомендована модель — Sonnet.

## Antigravity CLI, Codex CLI та інші агенти

Запустіть агента в папці з субтитрами й напишіть:

```
Переклади субтитри film.srt українською. Спочатку виконай
python3 /шлях/до/ai-subtitle-translator-uk/aisubs guide film.srt
і точно дотримуйся інструкції, яку вона виведе.
```

`aisubs guide` виводить покрокову інструкцію для агента з уже підставленими шляхами. Репозиторій достатньо склонувати: `git clone https://github.com/yar4ick/ai-subtitle-translator-uk`.

Перевірено з Antigravity CLI і Gemini 3.8 Flash: один такий переклад серії забирає близько 11% тижневої квоти Flash. Агент питатиме дозволу на кожну нову команду; дозволяйте виклики `python3 …/aisubs`.

## Вручну, через веб-чат

```bash
python3 aisubs prepare film.srt --wikipedia
python3 aisubs glossary film.srt            # вставте запит у чат, відповідь збережіть у glossary.txt
python3 aisubs glossary film.srt glossary.txt
python3 aisubs next film.srt                # вставте запит у чат, відповідь збережіть у answer.txt
python3 aisubs import film.srt answer.txt   # повторюйте next/import, доки всі частини не будуть перекладені
python3 aisubs fix film.srt                 # якщо перевірки знайшли помилки: запит на виправлення
python3 aisubs import film.srt fix.txt --fix
python3 aisubs assemble film.srt
```

Якщо `aisubs` встановлено (`pip install git+https://github.com/yar4ick/ai-subtitle-translator-uk`), замість `python3 aisubs` пишіть просто `aisubs`.

## Що вийде

- `film.uk.srt` — український переклад поруч з оригіналом;
- `film.aisubs/` — робоча папка: глосарій, переклади частин, звіт перевірок `report.txt`;
- `film.aisubs/review.txt` — сумнівні місця (модель не впевнена, хто говорить, або рядок не пройшов перевірку й після повтору). Виправте переклад у файлі й виконайте `aisubs review film.srt --apply`. Увага: там сцени з фільму, тож краще дивитися після перегляду.

Роботу можна перервати й продовжити будь-коли: `aisubs status film.srt` показує, на чому зупинилися.

## Обмеження

- Лише англійські субтитри і лише формат SRT.
- Мовців модель визначає з тексту, без звуку й відео. У наших тестах правильно в 94–100% рядків; сумнівні рядки позначаються для перегляду.
- Лайка перекладається з тією ж силою, що в оригіналі.
- Субтитри зазвичай захищені авторським правом: перекладайте для власного перегляду.

## Ліцензія

[MIT](LICENSE)

---

## English

Translate SRT subtitles from English into Ukrainian with an AI agent: Claude Code, Antigravity CLI (Gemini) or any other agent that can run commands. A manual mode for web chats is available too.

The model does the translation; a small tool, `aisubs` (Python, no dependencies), does everything else:
- splits subtitles into parts and scenes and computes how many characters fit each line's time on screen;
- builds a glossary: names, characters' gender, who addresses whom as «ти» or «ви», terms; optionally takes the cast from Wikipedia;
- checks the translation: length and reading speed, verb gender against the speaker, names, untranslated lines, Russian letters, tags;
- sends only the failing lines back to the model and collects doubtful places in a file for a person to review;
- assembles `film.uk.srt` with the original timings.

The model gets only the line text, without timings, and answers in a compact format, so token use is low. A 25-minute episode (290 subtitles) in Claude Code with Sonnet costs about $0.5 at API prices and takes 4–5 minutes.

## Requirements

- Python 3.10 or newer (nothing to install);
- English `.srt` subtitles;
- an AI agent or access to a chat model.

## Claude Code

Install the plugin once:

```
/plugin marketplace add yar4ick/ai-subtitle-translator-uk
/plugin install aisubs@aisubs
```

Go to the folder with the subtitles, start `claude` and type:

```
/aisubs:translate film.srt
```

You can add wishes after the file name, for example:
- `/aisubs:translate film.srt --wikipedia` — take the cast from Wikipedia (recommended for well-known films and series);
- `/aisubs:translate film.srt check the glossary with me` — show names, gender and ти/ви before translating and wait for your confirmation.

The agent runs all steps itself without permission prompts: the plugin pre-approves `aisubs` calls. Sonnet is the recommended model.

## Antigravity CLI, Codex CLI and other agents

Start the agent in the folder with the subtitles and write:

```
Translate the subtitles film.srt into Ukrainian. First run
python3 /path/to/ai-subtitle-translator-uk/aisubs guide film.srt
and follow the instructions it prints exactly.
```

`aisubs guide` prints step-by-step instructions for the agent with the paths filled in. Cloning the repository is enough: `git clone https://github.com/yar4ick/ai-subtitle-translator-uk`.

Tested with Antigravity CLI and Gemini 3.8 Flash: one episode takes about 11% of the weekly Flash quota. The agent asks permission for each new command; allow the `python3 …/aisubs` calls.

## Manual mode (web chat)

```bash
python3 aisubs prepare film.srt --wikipedia
python3 aisubs glossary film.srt            # paste the request into the chat, save the answer as glossary.txt
python3 aisubs glossary film.srt glossary.txt
python3 aisubs next film.srt                # paste the request into the chat, save the answer as answer.txt
python3 aisubs import film.srt answer.txt   # repeat next/import until all parts are translated
python3 aisubs fix film.srt                 # if the checks found problems: a request to fix them
python3 aisubs import film.srt fix.txt --fix
python3 aisubs assemble film.srt
```

With `aisubs` installed (`pip install git+https://github.com/yar4ick/ai-subtitle-translator-uk`), use `aisubs` instead of `python3 aisubs`.

## Output

- `film.uk.srt` — the Ukrainian translation next to the original;
- `film.aisubs/` — the working folder: glossary, translated parts, the check report `report.txt`;
- `film.aisubs/review.txt` — doubtful places (the model is unsure who speaks, or a line still fails a check after a retry). Fix the translation in the file and run `aisubs review film.srt --apply`. Note: it shows scenes of the film, so it is best read after watching.

Work can be interrupted and resumed at any time: `aisubs status film.srt` shows where it stopped.

## Limitations

- English subtitles and the SRT format only.
- The model works out who speaks from the text alone, without audio or video. In our tests it was right on 94–100% of lines; doubtful lines are marked for review.
- Swearing is translated with the same strength as in the original.
- Subtitles are usually copyrighted: translate them for your own viewing.

## License

[MIT](LICENSE)
