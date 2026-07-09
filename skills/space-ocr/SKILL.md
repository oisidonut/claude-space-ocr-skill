---
name: space-ocr
description: Turn document images (invoices, receipts, business cards, IDs, forms) into structured, queryable data using the space ocr REST API (https://api.space-ocr.com). Use when the user wants to extract fields from a scanned/photographed document, batch-process a folder of documents into a sheet, store extraction results without standing up a database, or answer questions about previously-scanned documents. Every value comes back with a verified on-page location (bounding box), so results can be cited and checked. Talks to the API with a dependency-free Python client — no pip install, no MCP server, no SDK.
---

# space ocr

space ocr reads a document image on its own servers and returns **structured fields**,
each tied to the **exact spot on the page** it was read from (a 4-point box re-anchored to
real Vision-API symbols, not an LLM guess). It also gives you **storage** — folders, sheets,
and rows — so the documents you process become a queryable workspace **without you building a
database or a vector store**. The API is the storage.

Everything is driven through one stdlib-only script: [`scripts/space_ocr.py`](scripts/space_ocr.py).
There is nothing to install — only `python3`.

## Setup

1. Get an API key at https://space-ocr.com → Developer → API Keys in the top menu (100 free scans, no card).
2. Put it where the script can read it — either:
   - `export SPACE_OCR_API_KEY=spocr_...`, or
   - a `.env` file in the project root (see [`.env.example`](.env.example)).
3. That's it. Test with `python3 scripts/space_ocr.py balance`.

Optional: `SPACE_OCR_API_BASE` overrides the endpoint (defaults to `https://api.space-ocr.com`).

## Commands

Run `python3 scripts/space_ocr.py <command> --help` for flags. All output is JSON on stdout.

| Command | What it does | Maps to |
|---|---|---|
| `balance` | Remaining free / flat-fee / paid scans | `GET /amount` |
| `ocr <image> [--auto \| --template ID \| --fields FILE]` | Extract fields from one image (URL, file path, or base64). Prefer `--auto`: the engine looks at the page and picks the fields itself, with the same gating as `/ocr/suggest_fields` (rejects non-text / non-document images instead of inventing fields) | `POST /ocr/fields` |
| `space [PATH] [--depth N]` | List the workspace tree | `GET /space` |
| `create folder\|sheet\|memo <PATH> <NAME> [--columns FILE]` | Make a folder / sheet (with column schema) / memo | `POST /create` |
| `upload <SHEET_PATH> <FILE...> [--wait]` | Drop images into a sheet; OCR runs server-side (async) | `POST /upload` |
| `job <JOB_ID>` | Poll an async upload's OCR status/result | `GET /jobs/{id}` |
| `view <PATH> [--where … --sort … --limit …]` | Read a folder's items or a sheet's rows; sheets support server-side filtering | `GET /view` |
| `query <SHEET> [--where … --sort … --limit …]` | Lean rows (boxes dropped) + the same filters, to answer questions | `GET /view` |
| `edit <PATH> --row R --column C --value V` / `edit <PATH> --text T` | Correct a sheet cell or rewrite a memo | `POST /edit` |
| `remove <PATH>` | Delete a folder / sheet / memo / image (cascades) | `POST /remove` |
| `templates` | List the built-in document templates | (local) |

**Picking the field schema — `--auto` is the default.** When you call `ocr`, prefer `--auto`:
the engine runs the same field-suggestion pass that `/ocr/suggest_fields` uses to pick
4–8 fields from what's actually printed on the page (and refuses to invent fields when
the image isn't a structured document). Use `--template <id>` only when the document is
clearly one of the built-ins (`invoice`, `receipt`, `business_card`, `purchase_order`,
`delivery`, `quote`, `bankbook`, `passport`, `driver_license`, `resident_card`,
`my_number_card`, `residence_card`, `india_electoral_roll_cover`) **and** you want the
template's curated prompt. Reach for `--fields <schema.json>` (see
[`assets/schema_invoice.json`](assets/schema_invoice.json)) only when you need a specific
column shape `--auto` won't produce.

**Paths:** folders are addressed by name (e.g. `/invoices`). **Sheets can be addressed by either
their name *or* the `uniqueKey` path that `create` returns** — `/invoices/march` and
`/invoices/8G90wq…` both work, as long as `march` is unique within `/invoices`. `create` rejects
a `name` that collides with any sibling (folder/sheet/memo/img) in the parent → `400
bad_request`. Sheet names may not contain `. / # $ [ ]`. The `uniqueKey` path is always safe and
permanent; prefer it when a name could be ambiguous (legacy data with duplicate sheet names in
the same parent returns `400 validation_failed: ambiguous sheet name` on a name-path lookup —
fall back to the `uniqueKey`). Memos are still keyed by `uniqueKey`.

## Calling the script

Three easy-to-trip-over notes when driving this from a shell:

- **No file extension on paths.** Use `/Invoices/Invoices`, not `/Invoices/Invoices.sheet`. Folders, sheets, memos, and images are all addressed the same way.
- **Windows: PowerShell or cmd, not Git Bash.** MSYS rewrites any argument starting with `/` into a Windows path before Python sees it (`/Invoices` → `C:/Program Files/Git/Invoices`), which the server rejects as `validation_failed`. The script warns when it spots this; the fix is the shell, not the arg.
- **Don't write a `_analyze.py` helper to parse the JSON.** `view` and `query` both take `--out FILE` (utf-8). Land the response in a file, read it back, reason over it inline — no second `python -c` invocation, and you sidestep Windows console code pages (cp949/cp1252) entirely.

## How to behave

These four rules are the point of the skill — they keep the agent lean, trustworthy, and
cheap. Follow them by default.

1. **Store, don't dump — default to upload.** For anything you might want to look at again,
   go `create sheet` → `upload`, not direct `ocr`. Pick the columns by sampling one document
   with `ocr <image> --auto` and reusing the result's top-level keys (an array-valued key
   becomes `{"type":"array","children":[<keys of the first row>]}`, everything else
   `"string"`); when the document is obviously a built-in type, `--template <id>` is the
   shortcut. Reserve a direct `ocr` call for transient one-off lookups you don't need to keep.

2. **Check before you scan.** Run `balance` before a batch and confirm there's enough quota for
   the number of files; if not, tell the user instead of burning scans halfway. Before
   re-scanning a document, check `space` / `view` — if it's already a row in a sheet, reuse it
   rather than spending another scan.

3. **Answer from stored rows, don't re-read.** To answer a question about already-processed
   documents ("which vendor billed the most?"), use `query <sheet>` to pull the stored rows and
   reason over those — do **not** re-OCR or re-open the source files. For a big sheet, push the
   work to the server with filters (`query <sheet> --where 'total>=40000' --sort total:desc
   --limit 20`) instead of dragging every row into context. The rows are the database; the
   `/view` filters are your SELECT — and they're free (reads don't cost a scan).

4. **Cite the location; flag what's uncertain.** Every value carries a `field_bboxes` location
   (and raw OCR carries a `confidence`). When you present an extracted value, mention where on
   the page it came from, and surface anything low-confidence or blank rather than asserting
   it's correct. Each `field_bboxes` entry may also carry **`text_verified`**: `true` means the
   Vision OCR symbols at that spot spell out exactly the returned value (two independent engines
   agree — near-certain), `false` means they disagree — call those cells out for a human check;
   absent means no signal. Note `query` drops boxes (and with them `text_verified`), so use
   `view` when you're verifying rather than just reading. Deep-link the user to the dashboard view with boxes drawn:
   `https://space-ocr.com/pages/myspace/<path>` (URL-encode each segment of the workspace
   path). **Prefer verbatim extraction:** when you write a custom schema, tell the model to
   copy each value exactly as printed (don't normalize dates/numbers or compute totals) —
   reformatted or derived values can't be anchored to the page, so their boxes drift. The
   simplest way to lock this in for a sheet is `create sheet --prompt "...verbatim..."` so
   every later `upload` to the sheet runs against the same instruction.

## Going deeper

The full endpoint spec — request/response shapes, error codes, the bounding-box coordinate
system (0–1000 normalized), the quota model, idempotency, webhooks — lives in
[`references/api.md`](references/api.md). Load it when you need a field name or an edge case;
you don't need it for the common flow above.
