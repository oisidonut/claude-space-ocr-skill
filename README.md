# space-ocr skill

Agent skill for [Claude Code](https://claude.com/claude-code) and
[Cursor](https://cursor.com) that extracts structured fields from document images
(invoices, receipts, business cards, IDs, forms) via the
[space ocr](https://space-ocr.com) REST API. Each extracted value carries the bounding
box on the page it was read from, and results are stored in a queryable workspace behind
the API instead of returned to the conversation as raw JSON.

## What you can do with it

| You ask | What the skill runs |
|---|---|
| *"Extract the vendor and total from this invoice."* | `ocr <image> --auto` |
| *"Process this folder of 30 receipts into a sheet."* | `create sheet` → `upload` (server-side OCR, async) |
| *"Which vendor billed the most last month?"* | `query <sheet> --where 'invoice_date>=2026-05-01' --sort total:desc` over the stored rows |
| *"Show me where on the page that number came from."* | `view <sheet>` returns each value's bounding box; deep-link `https://space-ocr.com/pages/myspace/<path>` |
| *"Fix row 4, column 'total' — it should be 12800."* | `edit <sheet> --row 4 --column total --value 12800` |

Python client is stdlib-only — no `pip install`, no MCP server, no SDK.

## Install

**Claude Code** (loads on demand):
```
/plugin marketplace add oisidonut/claude-space-ocr-skill
/plugin install space-ocr@space-ocr
```

**Cursor** — installs to `~/.cursor/skills/space-ocr/`:
```bash
# macOS / Linux
curl -fsSL https://raw.githubusercontent.com/oisidonut/claude-space-ocr-skill/main/scripts/install.sh | bash -s -- cursor
```
```powershell
# Windows (interactive)
iwr -useb https://raw.githubusercontent.com/oisidonut/claude-space-ocr-skill/main/scripts/install.ps1 | iex
# Windows (unattended)
& ([scriptblock]::Create((iwr -useb https://raw.githubusercontent.com/oisidonut/claude-space-ocr-skill/main/scripts/install.ps1).Content)) -Target cursor
```

For a project-scoped install (committed alongside the codebase), copy
`skills/space-ocr/` into `<your-project>/.cursor/skills/`.

## Setup

1. Create an API key at https://space-ocr.com → **Developer → API Keys** (top menu).
2. Either drop it in a `.env` next to the script (see
   [`.env.example`](skills/space-ocr/.env.example)) or export `SPACE_OCR_API_KEY=spocr_…`
   in your shell.
3. Smoke test:
   `python3 <install-root>/space-ocr/scripts/space_ocr.py balance`
   (Windows: use `py` instead of `python3`.)

Python 3.8+ on the host — the client runs locally, not inside the plugin sandbox, and uses
only the standard library. Override the endpoint with `SPACE_OCR_API_BASE` if you self-host.

## Picking fields — `--auto` first

The engine looks at the page and proposes 4–8 fields with the same gating as
`/ocr/suggest_fields` (it refuses non-document images instead of inventing fields), so
`--auto` is the default. Use `--template <id>` (`invoice`, `receipt`, `business_card`,
`purchase_order`, `delivery`, `quote`, `bankbook`, `passport`, `driver_license`,
`resident_card`, `my_number_card`, `residence_card`, `india_electoral_roll_cover`) when
the document is clearly one of those. Reach for a custom `--fields` schema only when you
need a shape `--auto` won't produce — example shapes:
[`schema_invoice.json`](skills/space-ocr/assets/schema_invoice.json),
[`schema_receipt.json`](skills/space-ocr/assets/schema_receipt.json),
[`schema_business_card.json`](skills/space-ocr/assets/schema_business_card.json).

## Behaviour rules

[`SKILL.md`](skills/space-ocr/SKILL.md) encodes four rules the agent follows on demand:

1. **Store, don't dump** — default to `create sheet` → `upload` so extractions stay citeable.
2. **Check before you scan** — `balance` first; reuse existing rows instead of re-OCRing.
3. **Answer from stored rows** — `query` with server-side filters; reads don't cost a scan.
4. **Cite the location; flag what's uncertain** — every value carries a `field_bboxes`.

## Repo layout

```
.claude-plugin/        # marketplace catalog + plugin manifest
scripts/               # install.sh / install.ps1
skills/space-ocr/
  SKILL.md             # behaviour rules + command table (loaded into agent context)
  scripts/space_ocr.py # API client (stdlib only)
  references/api.md    # full endpoint spec — loaded on demand
  assets/              # example field schemas (invoice / receipt / business_card)
  .env.example
```

## License

[MIT](LICENSE)
