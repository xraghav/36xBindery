"""36x Bindery — 36XFINANCE private PDF studio. Localhost only."""

from __future__ import annotations

import json
import os
import shutil
import sys
import threading
import time
import uuid
import webbrowser
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import engine


def _bundle_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent


def _data_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


ROOT = _bundle_root()
STATIC = ROOT / "static"
SESSIONS = _data_root() / ".sessions"
HOST = "127.0.0.1"
PORT = 8741
MAX_BYTES = 280 * 1024 * 1024
TTL_SECONDS = 4 * 60 * 60

def _packaged() -> bool:
    return bool(getattr(sys, "frozen", False))


def _asset_stamp() -> str:
    if _packaged():
        return "packaged"
    times = [p.stat().st_mtime_ns for p in STATIC.rglob("*") if p.is_file()]
    return str(max(times) if times else 0)


app = FastAPI(title="36x Bindery", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=STATIC), name="static")

_lock = threading.Lock()
_state: dict[str, dict] = {}


class RunBody(BaseModel):
    tool: str
    password: str = ""
    passwords: dict[str, str] = Field(default_factory=dict)
    file_id: str | None = None
    file_ids: list[str] = Field(default_factory=list)
    ranges: str = ""
    pages: list[int] = Field(default_factory=list)
    order: list[int] = Field(default_factory=list)
    every: int = 1
    degrees: int = 90
    watermark: str = ""
    new_password: str = ""
    title: str = ""
    author: str = ""
    subject: str = ""
    keywords: str = ""
    target_size: str = ""
    target_unit: str = "MB"


class OpenBody(BaseModel):
    password: str = ""


def _purge() -> None:
    now = time.time()
    with _lock:
        dead = [sid for sid, rec in _state.items() if now - rec["created"] > TTL_SECONDS]
        for sid in dead:
            shutil.rmtree(rec_path(sid), ignore_errors=True)
            _state.pop(sid, None)


def rec_path(sid: str) -> Path:
    return SESSIONS / sid


def require_session(sid: str) -> dict:
    _purge()
    with _lock:
        rec = _state.get(sid)
    if not rec:
        raise HTTPException(404, "Session expired. Drop the files again.")
    return rec


def file_entry(rec: dict, file_id: str) -> dict:
    for item in rec["files"]:
        if item["id"] == file_id:
            return item
    raise HTTPException(404, "That file is not in this session.")


def new_out(sid: str, name: str) -> Path:
    folder = rec_path(sid) / "out"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / name


@app.middleware("http")
async def _fresh_when_from_source(request, call_next):
    response = await call_next(request)
    if not _packaged():
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    html = (STATIC / "index.html").read_text(encoding="utf-8").replace("__ASSET_V__", _asset_stamp())
    return HTMLResponse(html)


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "local_only": True,
        "host": HOST,
        "port": PORT,
        "packaged": _packaged(),
        "app_window": os.environ.get("BINDERY_WINDOW") == "1",
    }


@app.post("/api/session")
def create_session() -> dict:
    _purge()
    sid = uuid.uuid4().hex
    path = rec_path(sid)
    (path / "uploads").mkdir(parents=True)
    with _lock:
        _state[sid] = {"created": time.time(), "files": []}
    return {"id": sid}


@app.post("/api/session/{sid}/files")
async def upload(sid: str, files: list[UploadFile] = File(...), password: str = Form("")):
    rec = require_session(sid)
    added = []
    for upload in files:
        name = Path(upload.filename or "document.pdf").name
        if not name.lower().endswith(".pdf"):
            raise HTTPException(400, f"{name} is not a PDF.")
        data = await upload.read()
        if len(data) > MAX_BYTES:
            raise HTTPException(400, f"{name} is larger than 280 MB.")
        fid = uuid.uuid4().hex[:12]
        dest = rec_path(sid) / "uploads" / f"{fid}.pdf"
        dest.write_bytes(data)
        locked = engine.needs_password(dest)
        pages = None
        error = None
        if not locked or password:
            try:
                pages = engine.page_count(dest, password)
            except engine.PdfError as exc:
                error = str(exc)
        item = {
            "id": fid,
            "name": name,
            "bytes": dest.stat().st_size,
            "pages": pages,
            "locked": locked,
            "error": error,
        }
        rec["files"].append(item)
        added.append(item)
    return {"files": added, "all": rec["files"]}


@app.get("/api/session/{sid}/files")
def list_files(sid: str) -> dict:
    rec = require_session(sid)
    return {"files": rec["files"]}


@app.delete("/api/session/{sid}/files/{fid}")
def remove_file(sid: str, fid: str) -> dict:
    rec = require_session(sid)
    rec["files"] = [f for f in rec["files"] if f["id"] != fid]
    path = rec_path(sid) / "uploads" / f"{fid}.pdf"
    path.unlink(missing_ok=True)
    return {"files": rec["files"]}


@app.get("/api/session/{sid}/files/{fid}/thumb/{page}")
def thumb(sid: str, fid: str, page: int, password: str = ""):
    rec = require_session(sid)
    item = file_entry(rec, fid)
    src = rec_path(sid) / "uploads" / f"{fid}.pdf"
    dest = rec_path(sid) / "thumbs" / f"{fid}_{page}.png"
    if not dest.exists():
        try:
            engine.render_thumb(src, page, password, dest)
        except engine.PdfError as exc:
            raise HTTPException(400, str(exc)) from exc
    return FileResponse(dest, media_type="image/png", filename=f"{item['name']}-p{page + 1}.png")


@app.post("/api/session/{sid}/files/{fid}/open")
def open_locked(sid: str, fid: str, body: OpenBody):
    rec = require_session(sid)
    item = file_entry(rec, fid)
    src = rec_path(sid) / "uploads" / f"{fid}.pdf"
    try:
        item["pages"] = engine.page_count(src, body.password)
        item["error"] = None
    except engine.PdfError as exc:
        raise HTTPException(400, str(exc)) from exc
    return item


@app.get("/api/session/{sid}/files/{fid}/info")
def file_info(sid: str, fid: str, password: str = ""):
    rec = require_session(sid)
    file_entry(rec, fid)
    src = rec_path(sid) / "uploads" / f"{fid}.pdf"
    try:
        return engine.info(src, password)
    except engine.PdfError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/session/{sid}/run")
def run(sid: str, body: RunBody) -> dict:
    rec = require_session(sid)
    try:
        result = _run(sid, rec, body)
    except engine.PdfError as exc:
        raise HTTPException(400, str(exc)) from exc
    rec["last"] = result
    (rec_path(sid) / "last.json").write_text(json.dumps(result), encoding="utf-8")
    return result


@app.get("/api/session/{sid}/download")
def download(sid: str):
    rec = require_session(sid)
    last = rec.get("last")
    if not last:
        raise HTTPException(404, "Nothing to download yet.")
    path = Path(last["path"])
    if not path.exists():
        raise HTTPException(404, "The result file was cleared.")
    return FileResponse(path, filename=last["filename"], media_type=last["media"])


def _src(sid: str, fid: str) -> Path:
    return rec_path(sid) / "uploads" / f"{fid}.pdf"


def _pw(body: RunBody, fid: str) -> str:
    return body.passwords.get(fid) or body.password or ""


def _one(rec: dict, body: RunBody) -> dict:
    if body.file_id:
        return file_entry(rec, body.file_id)
    if len(rec["files"]) == 1:
        return rec["files"][0]
    raise engine.PdfError("Choose one PDF for this tool.")


def _run(sid: str, rec: dict, body: RunBody) -> dict:
    tool = body.tool

    if tool == "merge":
        ids = body.file_ids or [f["id"] for f in rec["files"]]
        if len(ids) < 2:
            raise engine.PdfError("Add at least two PDFs to merge.")
        paths = [_src(sid, fid) for fid in ids]
        pws = [_pw(body, fid) for fid in ids]
        dest = new_out(sid, "merged.pdf")
        engine.merge(paths, pws, dest)
        return _result(dest, "merged.pdf", "application/pdf", extra={"pages": engine.page_count(dest)})

    item = _one(rec, body)
    fid = item["id"]
    src = _src(sid, fid)
    password = _pw(body, fid)
    stem = Path(item["name"]).stem
    total = engine.page_count(src, password)

    if tool == "split-range":
        indexes = engine.parse_ranges(body.ranges, total)
        dest = new_out(sid, f"{stem}-extract.pdf")
        engine.extract_pages(src, password, indexes, dest)
        return _result(dest, dest.name, extra={"pages": len(indexes)})

    if tool == "split-selected":
        indexes = engine.parse_indexes(body.pages, total)
        dest = new_out(sid, f"{stem}-pages.pdf")
        engine.extract_pages(src, password, indexes, dest)
        return _result(dest, dest.name, extra={"pages": len(indexes)})

    if tool == "split-all":
        dest = new_out(sid, f"{stem}-pages.zip")
        count = engine.explode(src, password, dest)
        return _result(dest, dest.name, "application/zip", extra={"files": count})

    if tool == "split-every":
        dest = new_out(sid, f"{stem}-chunks.zip")
        count = engine.split_every(src, password, body.every, dest)
        return _result(dest, dest.name, "application/zip", extra={"files": count})

    if tool == "reorder":
        order = [n - 1 for n in body.order] if body.order and min(body.order) >= 1 else body.order
        dest = new_out(sid, f"{stem}-reordered.pdf")
        engine.reorder(src, password, order, dest)
        return _result(dest, dest.name, extra={"pages": total})

    if tool == "drop":
        indexes = engine.parse_indexes(body.pages, total)
        dest = new_out(sid, f"{stem}-trimmed.pdf")
        engine.drop_pages(src, password, indexes, dest)
        return _result(dest, dest.name, extra={"removed": len(indexes)})

    if tool == "rotate":
        indexes = engine.parse_indexes(body.pages, total) if body.pages else list(range(total))
        dest = new_out(sid, f"{stem}-rotated.pdf")
        engine.rotate(src, password, indexes, body.degrees, dest)
        return _result(dest, dest.name, extra={"degrees": body.degrees})

    if tool == "compress":
        dest = new_out(sid, f"{stem}-compact.pdf")
        target = engine.parse_target_bytes(body.target_size, body.target_unit)
        stats = engine.compress(src, password, dest, target_bytes=target)
        return _result(dest, dest.name, extra=stats)

    if tool == "unlock":
        dest = new_out(sid, f"{stem}-unlocked.pdf")
        engine.unlock(src, password, dest)
        return _result(dest, dest.name)

    if tool == "lock":
        dest = new_out(sid, f"{stem}-locked.pdf")
        engine.lock(src, password, body.new_password, dest)
        return _result(dest, dest.name)

    if tool == "watermark":
        dest = new_out(sid, f"{stem}-mark.pdf")
        engine.watermark(src, password, body.watermark, dest)
        return _result(dest, dest.name)

    if tool == "text":
        dest = new_out(sid, f"{stem}.txt")
        pages = engine.extract_text(src, password, dest)
        return _result(dest, dest.name, "text/plain; charset=utf-8", extra={"pages": pages})

    if tool == "images":
        dest = new_out(sid, f"{stem}-images.zip")
        count = engine.extract_images(src, password, dest)
        return _result(dest, dest.name, "application/zip", extra={"images": count})

    if tool == "meta":
        dest = new_out(sid, f"{stem}-meta.pdf")
        engine.set_metadata(
            src,
            password,
            {
                "title": body.title,
                "author": body.author,
                "subject": body.subject,
                "keywords": body.keywords,
            },
            dest,
        )
        return _result(dest, dest.name)

    raise engine.PdfError(f"Unknown tool '{tool}'.")


def _result(path: Path, filename: str, media: str = "application/pdf", extra: dict | None = None) -> dict:
    payload = {
        "path": str(path),
        "filename": filename,
        "media": media,
        "bytes": path.stat().st_size,
    }
    if extra:
        payload.update(extra)
    return payload


def main() -> None:
    import uvicorn

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(line_buffering=True)
        except Exception:
            pass

    SESSIONS.mkdir(exist_ok=True)
    url = f"http://{HOST}:{PORT}"
    print(f"\n  36x Bindery is local-only at {url}", flush=True)
    if _packaged():
        print("  Running the packaged .exe (frozen snapshot). Rebuild to pick up source edits.\n", flush=True)
    else:
        print("  Running from source. Refresh the browser after UI edits; restart after Python edits.\n", flush=True)
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    if _packaged():
        uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
    else:
        uvicorn.run("server:app", host=HOST, port=PORT, log_level="warning", reload=True)


if __name__ == "__main__":
    main()
