# Changelog

## 0.3.0

- Removed the `--lang` flag from the `ocr` and `create` commands. The space ocr
  engine auto-detects the document's language(s); forcing language hints could
  bias Google Vision's recognition and misalign the word-level bounding boxes
  (`vertices`). The client no longer sends `languageHints`, and the
  `languageHints` parameter was dropped from the API, so passing it has no
  effect. `references/api.md` updated to drop the parameter.

## 0.2.4

- `/ocr/fields` request keys are now fully camelCase, matching the API's
  canonical naming: the client sends `imageType`, `templateId`, and
  `autoFields` instead of `image_type`, `template_id`, and `auto_fields`.
  The API still accepts the snake_case names as deprecated aliases, so older
  skill versions keep working. `references/api.md` updated to match.

## 0.2.3

- `/ocr/fields` language hints now use the API's canonical camelCase key:
  the client sends `languageHints` instead of `language_hints`, matching
  `/create`. The API still accepts `language_hints` as a deprecated alias,
  so older skill versions keep working. `references/api.md` updated to match.

## 0.2.2

- Added a top-level `description` to the marketplace manifest
  (`.claude-plugin/marketplace.json`) so the plugin surfaces with searchable
  keywords (OCR, invoice, receipt, business card, ID, form, bounding box,
  structured fields) in the Discover catalog. Clears the `claude plugin
  validate` warning.

## 0.2.1

- `view` and `query` accept `--out FILE` — writes the JSON response straight to
  a utf-8 file so agents can `Read` it instead of writing a throwaway analyzer
  script and piping through `python -c` (which crashes on Korean/Japanese
  Windows under cp949).
- Workspace-path arguments now warn when the value looks like a Git Bash (MSYS)
  auto-converted path (e.g. `/Invoices` rewritten to
  `C:/Program Files/Git/Invoices`). The request still goes through, but the
  hint short-circuits the generic `validation_failed` debugging loop.
- `query` / `view` URL-encoding: literal `/` in query params is preserved
  (the API rejects percent-encoded slashes), and the script forces utf-8 on
  stdout/stderr so non-ASCII vendor names don't break on Windows consoles.
- SKILL.md gains a "Calling the script" section naming the three gotchas up
  front: paths carry no file extension, Windows users want PowerShell over
  Git Bash, and `--out FILE` replaces the helper-script anti-pattern.

## 0.2.0

- `--auto` is now the default field-picking path. The skill teaches the agent to
  prefer `--auto` over `--template <id>` over a custom `--fields` schema.
  Server-side, `auto_fields=true` runs the same prompt that backs
  `/ocr/suggest_fields` before extraction, so non-document images are rejected
  rather than producing invented fields.
- Behaviour rule #1 reframed: default to `create sheet` → `upload` even for a
  single document, deriving columns from `ocr <image> --auto` output (top-level
  keys → columns; array values → `{type:"array", children:[first-row keys]}`).
- Behaviour rule #4 now points the agent at the dashboard URL pattern
  (`https://space-ocr.com/pages/myspace/<encoded-path>`) for citing extractions,
  and suggests pinning a verbatim prompt at sheet creation
  (`create sheet --prompt`) so every later upload runs against the same
  instruction.
- API reference: documented the two-pass behaviour and refund semantics for
  `auto_fields=true`.

## 0.1.0

- Initial release.
