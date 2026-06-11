#!/usr/bin/env python3
"""
space_ocr.py — dependency-free client for the space ocr public API.

No pip install. Python standard library only (urllib). Talks to https://api.space-ocr.com.

Auth:  export SPACE_OCR_API_KEY=spocr_...   (or put it in a .env file in the project root)
Base:  export SPACE_OCR_API_BASE=...        (optional; defaults to https://api.space-ocr.com)

Run `python3 space_ocr.py --help` for the command list.
"""

import argparse
import base64
import json
import mimetypes
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_BASE = "https://api.space-ocr.com"

# Built-in template ids (server-resolved). Kept here only for `templates` / --help convenience.
TEMPLATES = [
    "invoice", "receipt", "business_card", "purchase_order", "delivery",
    "quote", "bankbook", "passport", "driver_license", "resident_card",
    "my_number_card", "residence_card", "india_electoral_roll_cover",
]


# --------------------------------------------------------------------------- env / config

def _load_dotenv():
    """Minimal .env loader: looks at $SPACE_OCR_DOTENV, ./.env, and ../.env. Stdlib only."""
    candidates = []
    if os.environ.get("SPACE_OCR_DOTENV"):
        candidates.append(os.environ["SPACE_OCR_DOTENV"])
    candidates += [os.path.join(os.getcwd(), ".env"),
                   os.path.join(os.path.dirname(os.getcwd()), ".env")]
    for path in candidates:
        if not path or not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, val = line.partition("=")
                    key, val = key.strip(), val.strip().strip('"').strip("'")
                    os.environ.setdefault(key, val)
        except OSError:
            pass


def _config():
    _load_dotenv()
    key = os.environ.get("SPACE_OCR_API_KEY", "").strip()
    if not key:
        _die("SPACE_OCR_API_KEY is not set. Export it or add it to a .env file "
             "(see .env.example). Get one at https://space-ocr.com -> Developer -> API Keys (top menu).")
    base = os.environ.get("SPACE_OCR_API_BASE", DEFAULT_BASE).rstrip("/")
    return key, base


# --------------------------------------------------------------------------- http

def _request(method, path, *, json_body=None, query=None, multipart=None,
             idempotency_key=None):
    key, base = _config()
    url = base + path
    if query:
        clean = {k: v for k, v in query.items() if v is not None}
        if clean:
            # doseq=True so list values (e.g. multiple --where) become repeated params.
            # safe="/" keeps path values like "/Invoices/Invoices" literal — the API
            # rejects percent-encoded slashes with validation_failed.
            url += "?" + urllib.parse.urlencode(clean, doseq=True, safe="/")

    headers = {"Authorization": "Bearer " + key, "Accept": "application/json"}
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key

    data = None
    if multipart is not None:
        content_type, data = _encode_multipart(multipart["fields"], multipart["files"])
        headers["Content-Type"] = content_type
    elif json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = resp.read().decode("utf-8", "replace")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(raw)
        except ValueError:
            parsed = {"error": {"code": "http_%d" % exc.code, "message": raw[:500]}}
        err = parsed.get("error", parsed)
        _die("API %d %s: %s (requestId=%s)" % (
            exc.code, err.get("code", "?"), err.get("message", raw[:300]),
            err.get("requestId", "-")))
    except urllib.error.URLError as exc:
        _die("network error reaching %s: %s" % (url, exc.reason))


def _encode_multipart(fields, files):
    """Build a multipart/form-data body with the stdlib only."""
    boundary = "----spaceocr" + base64.urlsafe_b64encode(os.urandom(12)).decode("ascii").strip("=")
    crlf = b"\r\n"
    out = []
    for name, value in fields.items():
        if value is None:
            continue
        out += [b"--" + boundary.encode(),
                ('Content-Disposition: form-data; name="%s"' % name).encode(),
                b"", str(value).encode("utf-8")]
    for filepath in files:
        filename = os.path.basename(filepath)
        ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        with open(filepath, "rb") as fh:
            content = fh.read()
        out += [b"--" + boundary.encode(),
                ('Content-Disposition: form-data; name="files"; filename="%s"' % filename).encode(),
                ("Content-Type: %s" % ctype).encode(),
                b"", content]
    out += [b"--" + boundary.encode() + b"--", b""]
    return "multipart/form-data; boundary=" + boundary, crlf.join(out)


# --------------------------------------------------------------------------- helpers

def _die(msg):
    sys.stderr.write("error: " + msg + "\n")
    sys.exit(1)


_OUT_PATH = None  # set from `--out FILE` in main(); _emit writes there instead of stdout


def _emit(obj):
    text = json.dumps(obj, ensure_ascii=False, indent=2) + "\n"
    if _OUT_PATH:
        # Explicit utf-8 sidesteps Windows console code pages (cp949/cp1252) entirely,
        # so callers can `Read` the file directly instead of piping through another script.
        with open(_OUT_PATH, "w", encoding="utf-8") as fh:
            fh.write(text)
        sys.stdout.write(json.dumps(
            {"saved": _OUT_PATH, "bytes": len(text.encode("utf-8"))}) + "\n")
    else:
        sys.stdout.write(text)


_MSYS_PATH_RE = re.compile(r"^[A-Za-z]:[/\\]")


def _workspace_path(s):
    """argparse type for paths that address the space-ocr workspace tree.
    On Git Bash for Windows (MSYS), args starting with '/' get rewritten to a
    Windows path before Python sees them (e.g. /Invoices -> C:/Program Files/Git/Invoices),
    which then loses to a generic server validation_failed. Turn that into a clear
    hint while still sending the request — the server's 400 stays the final word."""
    if _MSYS_PATH_RE.match(s):
        sys.stderr.write(
            "warning: '%s' looks like a Git Bash (MSYS) auto-converted path. "
            "Workspace paths start with '/' (e.g. /Invoices/Invoices, no extension). "
            "Use PowerShell or cmd on Windows, or prefix the arg with '//' to bypass MSYS.\n"
            % s)
    return s


def _resolve_image(value):
    """Accept a URL, a local file path, a data: URI, or a raw base64 string."""
    if value.startswith(("http://", "https://")):
        return {"image": value, "imageType": "url"}
    if value.startswith("data:"):
        comma = value.find(",")
        return {"image": value[comma + 1:] if comma >= 0 else value, "imageType": "base64"}
    path = os.path.expanduser(value)
    if os.path.exists(path):
        with open(path, "rb") as fh:
            return {"image": base64.b64encode(fh.read()).decode("ascii"), "imageType": "base64"}
    # Not a path on disk -> assume it is already a base64 string.
    return {"image": value, "imageType": "base64"}


def _load_json_file(path):
    try:
        with open(os.path.expanduser(path), "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as exc:
        _die("could not read JSON from %s: %s" % (path, exc))


# Coordinate / diagnostic keys dropped by `query` so stored values stay lean for
# reasoning. The full boxes are still available via `view`.
_LEAN_DROP = {"field_bboxes", "bbox", "vertices", "bbox_source", "match_ratio"}


def _strip_boxes(obj):
    """Recursively drop coordinate/diagnostic keys (see _LEAN_DROP)."""
    if isinstance(obj, dict):
        return {k: _strip_boxes(v) for k, v in obj.items() if k not in _LEAN_DROP}
    if isinstance(obj, list):
        return [_strip_boxes(x) for x in obj]
    return obj


# --------------------------------------------------------------------------- commands

def cmd_balance(args):
    _emit(_request("GET", "/amount"))


def cmd_templates(args):
    _emit({"templates": TEMPLATES})


def cmd_ocr(args):
    img = _resolve_image(args.image)
    body = dict(img)
    if args.template:
        body["templateId"] = args.template
    if args.fields:
        spec = _load_json_file(args.fields)
        # Accept either a bare list of fields, or {"fields"/"columns": [...], "prompt": ...}
        if isinstance(spec, dict):
            body["fields"] = spec.get("fields") or spec.get("columns")
            if spec.get("prompt") and not args.prompt:
                body["prompt"] = spec["prompt"]
        else:
            body["fields"] = spec
    if args.auto:
        body["autoFields"] = True
    if args.prompt:
        body["prompt"] = args.prompt
    if args.lang:
        body["languageHints"] = [s.strip() for s in args.lang.split(",") if s.strip()]
    if not (body.get("fields") or body.get("templateId") or body.get("autoFields")):
        _die("provide one of --template, --fields, or --auto")
    _emit(_request("POST", "/ocr/fields", json_body=body,
                   idempotency_key=args.idempotency_key))


def cmd_space(args):
    _emit(_request("GET", "/space", query={"path": args.path, "depth": args.depth}))


def _row_query(args, boxes=None):
    """Build the /view query string from shared row-filter flags."""
    q = {"path": args.path}
    if getattr(args, "where", None):
        q["where"] = args.where          # list -> repeated ?where=
    if getattr(args, "sort", None):
        q["sort"] = args.sort
    if getattr(args, "select", None):
        q["select"] = args.select
    if getattr(args, "limit", None) is not None:
        q["limit"] = args.limit
    if getattr(args, "offset", None) is not None:
        q["offset"] = args.offset
    if boxes is not None:
        q["boxes"] = boxes
    elif getattr(args, "no_boxes", False):
        q["boxes"] = "0"
    return q


def cmd_view(args):
    _emit(_request("GET", "/view", query=_row_query(args)))


def cmd_query(args):
    """Lean 'answer from stored rows': server-side filter + bounding boxes dropped."""
    res = _request("GET", "/view", query=_row_query(args, boxes="0"))
    if res.get("type") != "sheet":
        _emit(res)
        return
    columns = [c.get("name") for c in res.get("columns", [])]
    rows = [{"rowKey": r.get("rowKey"), "name": r.get("name"),
             "ocrStatus": r.get("ocrStatus"),
             "values": _strip_boxes(r.get("values"))}  # defensive: server already dropped boxes
            for r in res.get("rows", [])]
    out = {"path": res.get("path"), "name": res.get("name"),
           "columns": columns, "rowCount": len(rows)}
    for k in ("total", "matched", "offset", "limit", "nextOffset"):
        if k in res:
            out[k] = res[k]
    out["rows"] = rows
    _emit(out)


def cmd_create(args):
    body = {"path": args.path, "type": args.type, "name": args.name}
    if args.type == "memo" and args.text is not None:
        body["text"] = args.text
    if args.type == "sheet" and args.columns:
        spec = _load_json_file(args.columns)
        if isinstance(spec, dict):
            body["columns"] = spec.get("columns") or spec.get("fields")
            if spec.get("prompt"):
                body["prompt"] = spec["prompt"]
        else:
            body["columns"] = spec
    if args.prompt:
        body["prompt"] = args.prompt
    if args.lang:
        body["languageHints"] = [s.strip() for s in args.lang.split(",") if s.strip()]
    _emit(_request("POST", "/create", json_body=body,
                   idempotency_key=args.idempotency_key))


def cmd_upload(args):
    for f in args.files:
        if not os.path.exists(os.path.expanduser(f)):
            _die("file not found: " + f)
    fields = {"path": args.path}
    if args.wait:
        fields["wait"] = "true"
    _emit(_request("POST", "/upload",
                   multipart={"fields": fields,
                              "files": [os.path.expanduser(f) for f in args.files]},
                   idempotency_key=args.idempotency_key))


def cmd_job(args):
    _emit(_request("GET", "/jobs/" + urllib.parse.quote(args.job_id)))


def cmd_edit(args):
    if args.text is not None:
        body = {"path": args.path, "text": args.text}
    else:
        if args.row is None or args.column is None:
            _die("sheet edit needs --row and --column and --value (or use --text for a memo)")
        body = {"path": args.path, "row": _maybe_int(args.row),
                "column": _maybe_int(args.column), "value": args.value}
    _emit(_request("POST", "/edit", json_body=body))


def cmd_remove(args):
    _emit(_request("POST", "/remove", json_body={"path": args.path}))


def _maybe_int(s):
    try:
        return int(s)
    except (TypeError, ValueError):
        return s


# --------------------------------------------------------------------------- cli

def build_parser():
    p = argparse.ArgumentParser(
        prog="space_ocr.py",
        description="Dependency-free client for the space ocr API (https://api.space-ocr.com).")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("balance", help="show remaining free / flat-fee / paid scans").set_defaults(func=cmd_balance)
    sub.add_parser("templates", help="list built-in template ids").set_defaults(func=cmd_templates)

    o = sub.add_parser("ocr", help="extract fields from one image")
    o.add_argument("image", help="URL, local file path, data: URI, or base64 string")
    o.add_argument("--auto", action="store_true",
                   help="preferred: let the engine pick the fields (same gating as /ocr/suggest_fields)")
    o.add_argument("--template", choices=TEMPLATES,
                   help="built-in template id — use when the doc clearly matches one of these")
    o.add_argument("--fields",
                   help="path to a JSON field/column schema — use only when --auto won't produce the shape you need")
    o.add_argument("--prompt", help="natural-language hint for the extractor")
    o.add_argument("--lang", help="comma-separated BCP-47 hints, e.g. ja,en")
    o.add_argument("--idempotency-key", dest="idempotency_key")
    o.set_defaults(func=cmd_ocr)

    s = sub.add_parser("space", help="list the workspace tree")
    s.add_argument("path", nargs="?", default="/", type=_workspace_path,
                   help="folder path (default /)")
    s.add_argument("--depth", type=int, default=1, help="1..10")
    s.set_defaults(func=cmd_space)

    def add_row_filters(sp):
        sp.add_argument("--where", action="append", metavar="EXPR",
                        help="row filter, e.g. 'total>=40000' or 'vendor~サクラ' "
                             "(repeatable; AND-ed). ops: = != > >= < <= ~")
        sp.add_argument("--sort", action="append", metavar="SPEC",
                        help="sort, e.g. 'total:desc' or 'invoice_date:asc' (repeatable). "
                             "for the -field shorthand pass it with '=': --sort=-total")
        sp.add_argument("--select", metavar="COLS", help="comma-separated columns to return")
        sp.add_argument("--limit", type=int, help="max rows (1..500)")
        sp.add_argument("--offset", type=int, help="rows to skip (pagination)")

    v = sub.add_parser("view", help="read a folder's items or a sheet's rows (with boxes)")
    v.add_argument("path", type=_workspace_path)
    add_row_filters(v)
    v.add_argument("--no-boxes", action="store_true", help="drop bounding boxes for a lean payload")
    v.add_argument("--out", metavar="FILE",
                   help="write the JSON response to FILE (utf-8) instead of stdout — "
                        "lets agents skip writing a helper script just to parse stdout")
    v.set_defaults(func=cmd_view)

    q = sub.add_parser("query", help="pull a sheet's rows lean (boxes stripped) for reasoning")
    q.add_argument("path", type=_workspace_path, help="sheet path")
    add_row_filters(q)
    q.add_argument("--out", metavar="FILE",
                   help="write the JSON response to FILE (utf-8) instead of stdout — "
                        "lets agents skip writing a helper script just to parse stdout")
    q.set_defaults(func=cmd_query)

    c = sub.add_parser("create", help="create a folder, sheet, or memo")
    c.add_argument("type", choices=["folder", "sheet", "memo"])
    c.add_argument("path", type=_workspace_path, help="parent folder path, e.g. /invoices")
    c.add_argument("name")
    c.add_argument("--columns", help="(sheet) path to a JSON column schema")
    c.add_argument("--text", help="(memo) body text")
    c.add_argument("--prompt", help="(sheet) extraction prompt applied to uploads")
    c.add_argument("--lang", help="comma-separated BCP-47 hints, e.g. ja,en")
    c.add_argument("--idempotency-key", dest="idempotency_key")
    c.set_defaults(func=cmd_create)

    u = sub.add_parser("upload", help="upload images into a sheet (OCR runs server-side)")
    u.add_argument("path", type=_workspace_path, help="destination SHEET path")
    u.add_argument("files", nargs="+", help="one or more image files (max 20)")
    u.add_argument("--wait", action="store_true", help="block until OCR finishes (else async)")
    u.add_argument("--idempotency-key", dest="idempotency_key")
    u.set_defaults(func=cmd_upload)

    j = sub.add_parser("job", help="poll an async upload's OCR job")
    j.add_argument("job_id")
    j.set_defaults(func=cmd_job)

    e = sub.add_parser("edit", help="correct a sheet cell, or rewrite a memo")
    e.add_argument("path", type=_workspace_path)
    e.add_argument("--row", help="row index (0-based) or row key")
    e.add_argument("--column", help="column index or name")
    e.add_argument("--value", help="new cell value")
    e.add_argument("--text", help="(memo) full replacement text")
    e.set_defaults(func=cmd_edit)

    r = sub.add_parser("remove", help="delete a folder/sheet/memo/image (cascades)")
    r.add_argument("path", type=_workspace_path)
    r.set_defaults(func=cmd_remove)

    return p


def main(argv=None):
    # On Windows the default console encoding is cp1252 and a JSON response
    # carrying non-ASCII (kanji, emoji, accented vendor names…) blows up with
    # UnicodeEncodeError. Force UTF-8 so callers don't need PYTHONIOENCODING.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args(argv)
    global _OUT_PATH
    _OUT_PATH = getattr(args, "out", None)
    args.func(args)


if __name__ == "__main__":
    main()
