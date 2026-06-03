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
| `ocr <image> [--template ID \| --fields FILE \| --auto]` | Extract fields from one image (URL, file path, or base64) | `POST /ocr/fields` |
| `space [PATH] [--depth N]` | List the workspace tree | `GET /space` |
| `create folder\|sheet\|memo <PATH> <NAME> [--columns FILE]` | Make a folder / sheet (with column schema) / memo | `POST /create` |
| `upload <SHEET_PATH> <FILE...> [--wait]` | Drop images into a sheet; OCR runs server-side (async) | `POST /upload` |
| `job <JOB_ID>` | Poll an async upload's OCR status/result | `GET /jobs/{id}` |
| `view <PATH> [--where … --sort … --limit …]` | Read a folder's items or a sheet's rows; sheets support server-side filtering | `GET /view` |
| `query <SHEET> [--where … --sort … --limit …]` | Lean rows (boxes dropped) + the same filters, to answer questions | `GET /view` |
| `edit <PATH> --row R --column C --value V` / `edit <PATH> --text T` | Correct a sheet cell or rewrite a memo | `POST /edit` |
| `remove <PATH>` | Delete a folder / sheet / memo / image (cascades) | `POST /remove` |
| `templates` | List the built-in document templates | (local) |

Built-in `--template` ids: `invoice`, `receipt`, `business_card`, `purchase_order`, `delivery`,
`quote`, `bankbook`, `passport`, `driver_license`, `resident_card`, `my_number_card`,
`residence_card`, `india_electoral_roll_cover`. For anything else, pass `--fields <schema.json>`
(see [`assets/schema_invoice.json`](assets/schema_invoice.json)) or `--auto` to let the engine
infer the fields.

**Paths:** folders are addressed by name (e.g. `/invoices`). **Sheets can be addressed by either
their name *or* the `uniqueKey` path that `create` returns** — `/invoices/march` and
`/invoices/8G90wq…` both work, as long as `march` is unique within `/invoices`. `create` rejects
a `name` that collides with any sibling (folder/sheet/memo/img) in the parent → `400
bad_request`. Sheet names may not contain `. / # $ [ ]`. The `uniqueKey` path is always safe and
permanent; prefer it when a name could be ambiguous (legacy data with duplicate sheet names in
the same parent returns `400 validation_failed: ambiguous sheet name` on a name-path lookup —
fall back to the `uniqueKey`). Memos are still keyed by `uniqueKey`.

## How to behave

These four rules are the point of the skill — they keep the agent lean, trustworthy, and
cheap. Follow them by default.

1. **Store, don't dump.** After extracting from more than one document, write the results into
   a space ocr **sheet** (`create sheet` once to define columns, then `upload` the images) —
   don't paste raw OCR JSON back into the conversation. The heavy data lives behind the API,
   not in the context window. For a true one-off single document, a direct `ocr` is fine.

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
   it's correct. Point the user to the space ocr web dashboard to see the boxes drawn on the
   document and verify by eye. **Prefer verbatim extraction:** when you write a custom schema,
   tell the model to copy each value exactly as printed (don't normalize dates/numbers or compute
   totals) — reformatted or derived values can't be anchored to the page, so their boxes drift.

## Going deeper

The full endpoint spec — request/response shapes, error codes, the bounding-box coordinate
system (0–1000 normalized), the quota model, idempotency, webhooks — lives in
[`references/api.md`](references/api.md). Load it when you need a field name or an edge case;
you don't need it for the common flow above.
