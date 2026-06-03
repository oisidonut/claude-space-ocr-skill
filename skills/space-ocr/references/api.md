# space ocr — public API reference

Full endpoint spec for the `space-ocr` skill. Load this only when you need an exact field name,
a response shape, or an edge case — the common flow is covered in `SKILL.md`.

- **Base URL:** `https://api.space-ocr.com` (override with `SPACE_OCR_API_BASE`)
- **Auth:** `Authorization: Bearer spocr_...` on every request except `GET /health`
- **Content type:** `application/json` everywhere except `POST /upload` (multipart/form-data)
- **Paths are unversioned** (no `/v1` prefix).

## Workspace model

A user's workspace ("MySpace") is a tree. Paths look like `/invoices/2024/march`. Node kinds:

- **folder** — contains other folders and items.
- **sheet** — a table with a fixed `columns` schema; each uploaded image becomes a **row**.
- **memo** — a text note.
- **img** — an image (usually a row inside a sheet).

The skill's "no database" property is exactly this: you `create` a sheet, `upload` images into
it, and the extracted rows live behind the API. You never stand up storage yourself.

## Endpoints

### `GET /health` — no auth
`{ "status": "ok", "version": "...", "time": 1730000000000 }`

### `GET /amount` — balance & quota
```json
{
  "free":    { "used": 12, "limit": 100, "remaining": 88, "cycleStart": 0, "cycleEnd": 0 },
  "flatfee": { "enabled": false, "used": 0, "limit": 0, "remaining": 0, "nextBillingAt": null },
  "balance": 0,
  "currency": "scans",
  "perCallCost": 1
}
```
Total scans you can run now = `free.remaining + (flatfee.enabled ? flatfee.remaining : 0) + balance`.
One OCR call (or one uploaded image) costs **1 scan**. Failed scans are auto-refunded.

### `POST /ocr/fields` — structured OCR for one image
Request:
```json
{
  "image": "<url | base64>",
  "image_type": "url",                 // "url" or "base64"
  "fields": [ { "name": "...", "type": "string|array", "description": "...", "children": [...] } ],
  "template_id": "invoice",            // OR a built-in template instead of fields
  "auto_fields": true,                 // OR let the engine infer the schema
  "prompt": "optional natural-language hint",
  "language_hints": ["ja", "en"]       // BCP-47; English is always auto-included
}
```
Supply **exactly one** of `fields`, `template_id`, or `auto_fields`. Supports an
`Idempotency-Key` header (a retry with the same key replays the cached result, no double charge).

**`auto_fields=true` runs in two passes server-side:** first the engine looks at the image
with the same prompt that backs internal field-suggestion (with rejection gates for "no
extractable text" and "not a structured document") and proposes 4–8 fields; then the standard
structured-OCR pipeline runs against that derived schema. If the image fails the gate (a
landscape photo, an empty page, an unstructured snapshot), the call returns
`ocr_engine_error` instead of inventing fields, and the scan is refunded — same charging
behaviour as any other failed `/ocr/fields` call.

Response — the engine result, passed through verbatim under `data`:
```json
{
  "status": "success",
  "data": {
    "vendor": "ACME Co.",
    "total": "12,800",
    "field_bboxes": {
      "vendor": { "bbox": {"xmin":145,"ymin":134,"xmax":320,"ymax":149},
                  "vertices": [ {"x":145,"y":134}, "..." ],
                  "match_ratio": 1.0, "bbox_source": "token_id" },
      "total":  { "bbox": {"xmin":540,"ymin":620,"xmax":593,"ymax":640} }
    }
  }
}
```
For an `array` field (repeating rows like line items) the value is a list, and each element
carries its own `field_bboxes` for the child columns. Raw text regions also include a
`confidence` (0.0–1.0).

### `GET /space?path=/&depth=1` — list the tree
`depth` is 1–10. Returns a flat array of nodes:
```json
[ { "path": "/invoices", "name": "invoices", "type": "folder", "createdAt": 0 },
  { "path": "/invoices/march", "name": "march", "type": "sheet", "uniqueKey": "abc", "extensions": "sheet" } ]
```

### `POST /create` — folder, sheet, or memo
```json
{
  "path": "/invoices",                 // parent folder (must exist; "/" is root)
  "type": "folder | sheet | memo",
  "name": "march",
  "text": "...",                       // memo only
  "columns": [ {"name":"vendor","type":"string","description":"..."},
               {"name":"items","type":"array","children":[ {"name":"qty","type":"string"} ]} ],
  "prompt": "...",                     // sheet: extraction prompt applied to every upload
  "languageHints": ["ja","en"]
}
```
Returns `201 { "path": "/invoices/<uniqueKey>", "type": "sheet", "uniqueKey": "..." }`.
A column schema uses the **same shape** as OCR `fields` (`name` / `type` / `description` /
`children`). Idempotency-Key supported.

> **Addressing:** sheets can be addressed by **either** their `name` **or** the `uniqueKey` that
> `create` returns — `/invoices/march` and `/invoices/<uniqueKey>` both resolve on every endpoint
> that takes a `path` (`/view`, `/upload`, `/edit`, `/remove`, …). Constraints:
> - **Sibling uniqueness:** within a parent folder, a name must be unique across all child kinds
>   (folder/sheet/memo/img). `POST /create` rejects a collision with
>   `400 bad_request: name already used by ... in parent`.
> - **Forbidden chars** in sheet names (same rule as folders): `. / # $ [ ]` →
>   `400 validation_failed: name contains forbidden chars`.
> - **Legacy ambiguity:** older data may have two sheets with the same name under one parent. A
>   name-path lookup on those returns `400 validation_failed: ambiguous sheet name "<name>"` —
>   use the `uniqueKey` path instead.
>
> Memos are still keyed by `uniqueKey`. Prefer the `uniqueKey` path in code paths where collisions
> or renames could surprise you; the name path is the convenient one for humans and one-off CLI use.

### `POST /upload` — images into a sheet (multipart)
Form fields: `path` (must be a **sheet** path), `files` (one or more; max 20, 20 MB each),
optional `wait=true`. OCR runs server-side using the sheet's `columns` + `prompt`.

Async (default) → returns job handles:
```json
{ "path": "/invoices/march",
  "jobs": [ { "uniqueKey": "...", "originalName": "a.jpg", "jobId": "job_...", "status": "pending" } ] }
```
With `wait=true` → blocks (~30s budget) and returns `results` with each `result` inline.
Quota for the whole batch is checked up front; if short, you get `402 insufficient_balance`
with a `processable` count and nothing is charged.

### `GET /jobs/{jobId}` — poll an async upload
```json
{ "jobId": "job_abc", "uniqueKey": "abc", "path": "/invoices/march", "sheetRef": "...",
  "status": "pending | processing | done | failed",
  "result": { "...": "engine result, present when done" },
  "imageUrl": "https://...", "createdAt": 0 }
```

### `GET /view?path=...` — read contents
- folder → `{ "type":"folder", "path", "items":[ {path,name,type,uniqueKey} ] }`
- sheet  → `{ "type":"sheet", "path", "name", "columns":[...], "total", "matched", "offset",
              "limit", "nextOffset", "rows":[ {rowKey, name, imageUrl, ocrStatus, values} ] }`
  where each `values` is the restored engine result (real column names + nested `field_bboxes`).
- memo   → `{ "type":"memo", "path", "name", "text" }`
- img    → `{ "type":"img", "path", "name", "imageUrl", "ocrStatus" }`

**Sheet query params** — server-side filtering over the rows. This is **free** (a read; no OCR,
no scan). Ignored for folders/memos/images.

| param | meaning |
|---|---|
| `where` | filter, e.g. `total>=40000`, `vendor~サクラ`, `ocrStatus=done`. Repeatable → AND-ed. Ops: `= != > >= < <= ~`(contains). Matches sheet columns plus `name`/`ocrStatus`. Numeric when both sides parse as numbers (commas/¥ stripped), else string compare. |
| `sort` | `total:desc` / `-invoice_date` / `invoice_date:asc`. Repeatable for tie-breaks. |
| `select` | comma-separated columns to return (projection), e.g. `vendor,total`. |
| `limit`, `offset` | pagination; `limit` is capped at 500. The response carries `total` (all rows), `matched` (after `where`), and `nextOffset` (null when exhausted). |
| `boxes` | `0`/`false` drops `field_bboxes`/`vertices`/`bbox` for a lean payload. |

Example: `GET /view?path=/invoices/<key>&where=total>=40000&sort=-total&limit=20&boxes=0`
With no params, `/view` returns every row unchanged (the counters are just additive).

### `POST /edit` — fix a cell or a memo
Sheet cell: `{ "path", "row": <index|key>, "column": <index|name>, "value": <any> }`
→ `{ "ok": true, "patched": { "row","column","value" } }`. (`field_bboxes` is not editable.)
Memo: `{ "path", "text": "..." }`.

### `POST /remove` — delete (cascades)
`{ "path": "/invoices/march" }` → `{ "ok": true }`. Removing a folder/sheet deletes its
children and the underlying stored images.

### Webhooks (brief)
`GET/PUT/DELETE /webhook` manage one space-wide webhook; `POST /webhook/test` sends a test
event; `GET /webhooks/deliveries[/ {id} [/redeliver]]` inspect/redeliver deliveries. Events
include `item.created` and flat-row changes. Not needed for the core extract→store→query flow.

## Errors

Every error has the same envelope and an HTTP status:
```json
{ "error": { "code": "validation_failed", "message": "...", "requestId": "..." }, "details": { } }
```
Common codes: `invalid_api_key` (401), `key_inactive` (401), `validation_failed` (400),
`bad_request` (400), `not_found` (404), `insufficient_balance` (402), `forbidden` (403),
`ocr_engine_error` (5xx). Rate limit → `429` (watch the `X-RateLimit-Remaining` header).

## Bounding-box coordinate system

All boxes are **0–1000 normalized** against the image, so they're resolution-independent:
```
pixel_x = bbox_x / 1000 * image_width
pixel_y = bbox_y / 1000 * image_height
```
- `bbox` = axis-aligned `{xmin,ymin,xmax,ymax}`; `vertices` = 4 points (handles rotated text).
- A row's `bbox`/`vertices` is the union of its matched fields; `field_bboxes` is per-column.
- `bbox_source`: `token_id` (LLM word-id → Vision word box, the deterministic path) or
  `vision_symbol_match` (character-level fallback). Boxes are re-anchored to real Vision-API
  symbols — **not** LLM-invented — which is why they can be trusted for verification UIs.

## Built-in templates (`template_id`)

`invoice`, `receipt`, `business_card`, `purchase_order`, `delivery`, `quote`, `bankbook`,
`passport`, `driver_license`, `resident_card`, `my_number_card`, `residence_card`,
`india_electoral_roll_cover`. Each resolves to a curated `fields` + `prompt` server-side.

## Design note — querying lives on `/view`, not a separate search product

The sheet **is** the database; its rows **are** the index. There is no separate `/search`
endpoint and there doesn't need to be — querying is a **filter on the store** (`/view` with
`where`/`sort`/`limit`/`offset`/`select`), not a bolted-on search/index service.

Two consumers, one mechanism:
- **An agent** answers fuzzy/natural-language questions by pulling rows and reasoning. For small
  sheets it can pull them all; for large ones it should push `where`/`limit` to the server so it
  doesn't drag every row into context. (The `query` command also drops boxes by default.)
- **A non-agent app** (dashboard, BI, another service) gets `where`/`sort`/`limit`/`offset` to do
  structured filtering and pagination without shipping the whole sheet client-side — which
  becomes *required*, not just convenient, once a sheet has many thousands of rows.

`/view` filtering is **free** — scans bill OCR work (`/ocr`, `/upload`), not reads. Cost and
abuse are bounded by rate limiting and the `limit` cap (max 500), not by charging per query.
Heavier server-side aggregation, if ever added at scale, would be a separate metered tier — kept
distinct from OCR scans. Flow stays: extract → store in a sheet → `view`/`query` (filter) → reason.
