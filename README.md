# space-ocr skill

A drop-in **agent skill** that turns document images — invoices, receipts, business cards,
IDs, forms — into **structured fields**, each anchored to its exact spot on the page (a
verified bounding box, not an LLM guess).

It also gives the agent a **queryable workspace** out of the box: folders, sheets, and rows
live behind the [space ocr](https://space-ocr.com) API, so you can batch-process hundreds of
documents into a sheet and then ask questions over the stored rows — **without standing up a
database or a vector store**.

- Works in **[Claude Code](https://claude.com/claude-code)** and **[Cursor](https://cursor.com)** — both adopt the same SKILL.md format.
- No `pip install`, no MCP server, no SDK — just `python3` and an API key.
- 100 free scans on signup, no card required.
- Every extracted value is citeable: re-anchored to real Vision-API symbols, not invented.

## Install

### Claude Code

```
/plugin marketplace add oisidonut/claude-space-ocr-skill
/plugin install space-ocr@space-ocr
```

Claude Code loads the skill on demand whenever a task involves scanned documents.

### Cursor

Cursor reads the same `SKILL.md` format from `~/.cursor/skills/` (user-level) or
`.cursor/skills/` (project-level). One-line install:

**macOS / Linux:**
```bash
curl -fsSL https://raw.githubusercontent.com/oisidonut/claude-space-ocr-skill/main/scripts/install.sh | bash -s -- cursor
```

**Windows (PowerShell):**
```powershell
iwr -useb https://raw.githubusercontent.com/oisidonut/claude-space-ocr-skill/main/scripts/install.ps1 | iex
```

Or do it by hand:
```bash
git clone https://github.com/oisidonut/claude-space-ocr-skill.git
cp -r claude-space-ocr-skill/skills/space-ocr ~/.cursor/skills/
```

For project-scoped install (committed to the repo so the whole team gets it), copy into
`<your-project>/.cursor/skills/space-ocr/` instead.

## Requirements

Python 3.8+ on your machine — the client script runs locally, not inside the plugin sandbox.
The command is `python3` on macOS/Linux and `py` on Windows (install from
[python.org](https://www.python.org/downloads/)).

## Setup (one-time)

1. Get an API key at https://space-ocr.com → Developer → API Keys (top menu).
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

   **Claude Code, macOS / Linux:**
   ```bash
   python3 ~/.claude/plugins/space-ocr/skills/space-ocr/scripts/space_ocr.py balance
   ```
   **Claude Code, Windows (PowerShell):**
   ```powershell
   py $HOME\.claude\plugins\space-ocr\skills\space-ocr\scripts\space_ocr.py balance
   ```
   **Cursor, macOS / Linux:**
   ```bash
   python3 ~/.cursor/skills/space-ocr/scripts/space_ocr.py balance
   ```
   **Cursor, Windows (PowerShell):**
   ```powershell
   py $HOME\.cursor\skills\space-ocr\scripts\space_ocr.py balance
   ```

Optional: `SPACE_OCR_API_BASE` overrides the endpoint (defaults to `https://api.space-ocr.com`).

## What the agent can do with it

Just ask in natural language. The skill exposes a small command surface:

| You ask | What happens behind the scenes |
|---|---|
| *"Extract the vendor and total from this invoice."* | `ocr <image> --auto` (engine picks the fields; `--template invoice` is fine when you want the curated invoice prompt) |
| *"Process this folder of 30 receipts into a sheet."* | `create sheet` → `upload` (server-side OCR, async) — preferred even for a single doc |
| *"Which vendor billed the most last month?"* | `query <sheet> --where 'invoice_date>=2026-05-01' --sort total:desc` over the **stored rows** — no re-scanning |
| *"Show me where on the page that number came from."* | `view <sheet>` returns each value's bounding box (0–1000 normalized coords) |
| *"Fix row 4, column 'total' — it should be 12800."* | `edit <sheet> --row 4 --column total --value 12800` |

**Picking fields — `--auto` first.** The engine runs the same field-suggestion pass that
backs `/ocr/suggest_fields` (rejects non-document images instead of inventing fields), so
`--auto` is the default for anything that isn't an obvious template match. Use a built-in
`--template` id (`invoice`, `receipt`, `business_card`, `purchase_order`, `delivery`, `quote`,
`bankbook`, `passport`, `driver_license`, `resident_card`, `my_number_card`, `residence_card`,
`india_electoral_roll_cover`) when you want the template's curated prompt; reach for a custom
`--fields` schema (see [`schema_invoice.json`](skills/space-ocr/assets/schema_invoice.json) for
the shape) only when you need a specific column shape `--auto` won't produce.

## Why a skill (and not just an API wrapper)?

The skill teaches the agent **how to behave** with the API, not just how to call it:

1. **Store, don't dump — default to upload.** Results go into a sheet (`create sheet` → `upload`)
   even for a single doc, so every extraction stays citeable via `view`/`query`. Direct `ocr` is
   reserved for transient one-off lookups.
2. **Check before you scan** — `balance` before a batch; reuse existing rows instead of re-OCRing.
3. **Answer from stored rows** — for questions about already-processed documents, `query` the
   sheet with server-side filters (free reads) instead of pulling everything into context.
4. **Cite the location; flag what's uncertain** — every value carries a `field_bboxes`; low
   confidence or blanks get surfaced rather than silently asserted.

These are encoded in [`SKILL.md`](skills/space-ocr/SKILL.md). Both Claude Code and Cursor read
the same file on demand when the skill activates.

## What's in this repo

```
.claude-plugin/
  ├── marketplace.json       # Claude marketplace catalog
  └── plugin.json            # Claude plugin manifest
scripts/
  ├── install.sh             # one-line install for Claude Code or Cursor (Unix)
  └── install.ps1            # one-line install for Claude Code or Cursor (Windows)
skills/space-ocr/
  ├── SKILL.md               # behaviour rules + command table (loaded into agent context)
  ├── scripts/space_ocr.py   # stdlib-only API client (no deps)
  ├── references/api.md      # full endpoint spec — loaded on demand for edge cases
  ├── assets/                # example field schema
  └── .env.example
```

## Other agents (Copilot, Codex, Antigravity)

Cross-platform support beyond Claude Code and Cursor is on the roadmap. If you'd like to use
space-ocr from another agent (GitHub Copilot, OpenAI Codex, Google Antigravity, etc.), please
open an issue — the underlying Python client is portable, and an MCP server wrap is the most
likely next step.

## License

[MIT](LICENSE)
