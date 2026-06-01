# claude-space-ocr-skill

A [Claude Code](https://claude.com/claude-code) plugin that turns document images — invoices,
receipts, business cards, IDs, forms — into **structured fields**, each anchored to its exact
spot on the page (a verified bounding box, not an LLM guess).

It also gives Claude a **queryable workspace** out of the box: folders, sheets, and rows live
behind the [space ocr](https://space-ocr.com) API, so you can batch-process hundreds of documents
into a sheet and then ask questions over the stored rows — **without standing up a database or a
vector store**.

- No `pip install`, no MCP server, no SDK — just `python3` and an API key.
- 100 free scans on signup, no card required.
- Every extracted value is citeable: re-anchored to real Vision-API symbols, not invented.

## Install

```
/plugin marketplace add oisidonut/claude-space-ocr-skill
/plugin install space-ocr@space-ocr
```

That's it — Claude Code will load the skill on demand whenever a task involves scanned documents.

## Requirements

Python 3.8+ on your machine — the client script runs locally, not inside the plugin sandbox.
The command is `python3` on macOS/Linux and `py` on Windows (install from
[python.org](https://www.python.org/downloads/)).

## Setup (one-time)

1. Get an API key at https://space-ocr.com → Settings → API Keys.
2. Make it visible to the script — either drop it in a `.env` file in your project root
   (see [`.env.example`](skills/space-ocr/.env.example)), or export it in your shell:

   macOS / Linux (bash/zsh):
   ```bash
   export SPACE_OCR_API_KEY=spocr_...
   ```
   Windows (PowerShell):
   ```powershell
   $env:SPACE_OCR_API_KEY = "spocr_..."
   ```
3. Smoke test:

   macOS / Linux:
   ```bash
   python3 ~/.claude/plugins/space-ocr/skills/space-ocr/scripts/space_ocr.py balance
   ```
   Windows (PowerShell):
   ```powershell
   py $HOME\.claude\plugins\space-ocr\skills\space-ocr\scripts\space_ocr.py balance
   ```

Optional: `SPACE_OCR_API_BASE` overrides the endpoint (defaults to `https://api.space-ocr.com`).

## What Claude can do with it

Just ask in natural language. The skill exposes a small command surface to Claude:

| You ask | What happens behind the scenes |
|---|---|
| *"Extract the vendor and total from this invoice."* | `ocr <image> --template invoice` |
| *"Process this folder of 30 receipts into a sheet."* | `create sheet` → `upload` (server-side OCR, async) |
| *"Which vendor billed the most last month?"* | `query <sheet> --where 'invoice_date>=2026-05-01' --sort total:desc` over the **stored rows** — no re-scanning |
| *"Show me where on the page that number came from."* | `view <sheet>` returns each value's bounding box (0–1000 normalized coords) |
| *"Fix row 4, column 'total' — it should be 12800."* | `edit <sheet> --row 4 --column total --value 12800` |

Built-in document templates: `invoice`, `receipt`, `business_card`, `purchase_order`, `delivery`,
`quote`, `bankbook`, `passport`, `driver_license`, `resident_card`, `my_number_card`,
`residence_card`, `india_electoral_roll_cover`. For anything else, supply a custom field schema
(see [`schema_invoice.json`](skills/space-ocr/assets/schema_invoice.json) for the shape) or let
the engine infer fields with `--auto`.

## Why a skill (and not just an API wrapper)?

The skill teaches Claude **how to behave** with the API, not just how to call it:

1. **Store, don't dump** — after extracting from more than one document, results go into a sheet,
   not back into the conversation. The heavy data lives behind the API.
2. **Check before you scan** — `balance` before a batch; reuse existing rows instead of re-OCRing.
3. **Answer from stored rows** — for questions about already-processed documents, `query` the
   sheet with server-side filters (free reads) instead of pulling everything into context.
4. **Cite the location; flag what's uncertain** — every value carries a `field_bboxes`; low
   confidence or blanks get surfaced rather than silently asserted.

These are encoded in [`SKILL.md`](skills/space-ocr/SKILL.md). Claude reads them when the skill
activates.

## What's in this repo

```
.claude-plugin/
  ├── marketplace.json     # marketplace catalog (one plugin: space-ocr)
  └── plugin.json          # plugin manifest
skills/space-ocr/
  ├── SKILL.md             # behavior rules + command table (loaded into Claude's context)
  ├── scripts/space_ocr.py # stdlib-only API client (no deps)
  ├── references/api.md    # full endpoint spec — loaded on demand for edge cases
  ├── assets/              # example field schema
  └── .env.example
```

## Manual install (without the marketplace)

If you'd rather not use the plugin marketplace, just clone the repo and copy the skill into your
Claude config:

```bash
git clone https://github.com/oisidonut/claude-space-ocr-skill.git
cp -r claude-space-ocr-skill/skills/space-ocr ~/.claude/skills/
```

Or symlink it for live updates while you `git pull`.

## License

[MIT](LICENSE)