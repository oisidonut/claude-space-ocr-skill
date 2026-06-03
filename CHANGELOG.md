# Changelog

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
