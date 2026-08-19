"""Local PDF operations. Nothing here talks to the network."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

import fitz
import pikepdf

RANGE_TOKEN = re.compile(r"^\s*(\d+)\s*(?:-\s*(\d+))?\s*$")


class PdfError(ValueError):
    pass


def open_doc(path: Path, password: str = "") -> fitz.Document:
    doc = fitz.open(path)
    if doc.needs_pass:
        if not password:
            doc.close()
            raise PdfError("This PDF is locked. Enter the password, then try again.")
        if not doc.authenticate(password):
            doc.close()
            raise PdfError("The password did not unlock this PDF.")
    return doc


def page_count(path: Path, password: str = "") -> int:
    doc = open_doc(path, password)
    try:
        return doc.page_count
    finally:
        doc.close()


def needs_password(path: Path) -> bool:
    doc = fitz.open(path)
    locked = bool(doc.needs_pass)
    doc.close()
    return locked


def info(path: Path, password: str = "") -> dict:
    doc = open_doc(path, password)
    try:
        meta = doc.metadata or {}
        return {
            "pages": doc.page_count,
            "encrypted": bool(doc.is_encrypted),
            "title": meta.get("title") or "",
            "author": meta.get("author") or "",
            "subject": meta.get("subject") or "",
            "creator": meta.get("creator") or "",
            "producer": meta.get("producer") or "",
            "keywords": meta.get("keywords") or "",
            "page_width": round(doc[0].rect.width, 1) if doc.page_count else 0,
            "page_height": round(doc[0].rect.height, 1) if doc.page_count else 0,
        }
    finally:
        doc.close()


def parse_ranges(spec: str, total: int) -> list[int]:
    """1-based ranges like '1-3, 5, 8-10' → 0-based unique ordered indexes."""
    if not spec.strip():
        raise PdfError("Enter page ranges, for example 1-3, 5, 8-10.")
    seen: set[int] = set()
    out: list[int] = []
    for raw in spec.split(","):
        m = RANGE_TOKEN.match(raw)
        if not m:
            raise PdfError(f"Could not read page range '{raw.strip()}'.")
        start = int(m.group(1))
        end = int(m.group(2) or start)
        if start > end:
            start, end = end, start
        if start < 1 or end > total:
            raise PdfError(f"Pages must be between 1 and {total}. Got {start}-{end}.")
        for n in range(start, end + 1):
            i = n - 1
            if i not in seen:
                seen.add(i)
                out.append(i)
    if not out:
        raise PdfError("No pages selected.")
    return out


def parse_indexes(pages: list[int], total: int) -> list[int]:
    out: list[int] = []
    seen: set[int] = set()
    for n in pages:
        if not isinstance(n, int) or n < 1 or n > total:
            raise PdfError(f"Page {n} is outside 1–{total}.")
        i = n - 1
        if i not in seen:
            seen.add(i)
            out.append(i)
    if not out:
        raise PdfError("Select at least one page.")
    return out


def render_thumb(path: Path, page: int, password: str, dest: Path, width: int = 220) -> None:
    doc = open_doc(path, password)
    try:
        if page < 0 or page >= doc.page_count:
            raise PdfError("That page does not exist.")
        pix = doc[page].get_pixmap(matrix=fitz.Matrix(width / doc[page].rect.width, width / doc[page].rect.width), alpha=False)
        dest.parent.mkdir(parents=True, exist_ok=True)
        pix.save(dest)
    finally:
        doc.close()


def merge(paths: list[Path], passwords: list[str], dest: Path) -> None:
    if len(paths) < 2:
        raise PdfError("Drop at least two PDFs to merge.")
    out = fitz.open()
    try:
        for path, password in zip(paths, passwords):
            src = open_doc(path, password)
            try:
                out.insert_pdf(src)
            finally:
                src.close()
        dest.parent.mkdir(parents=True, exist_ok=True)
        out.save(dest, garbage=4, deflate=True)
    finally:
        out.close()


def extract_pages(path: Path, password: str, indexes: list[int], dest: Path) -> None:
    src = open_doc(path, password)
    try:
        out = fitz.open()
        try:
            for i in indexes:
                out.insert_pdf(src, from_page=i, to_page=i)
            dest.parent.mkdir(parents=True, exist_ok=True)
            out.save(dest, garbage=4, deflate=True)
        finally:
            out.close()
    finally:
        src.close()


def explode(path: Path, password: str, dest_zip: Path) -> int:
    src = open_doc(path, password)
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(dest_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for i in range(src.page_count):
                one = fitz.open()
                one.insert_pdf(src, from_page=i, to_page=i)
                buf = one.tobytes(garbage=4, deflate=True)
                one.close()
                zf.writestr(f"page-{i + 1:04d}.pdf", buf)
        return src.page_count
    finally:
        src.close()


def split_every(path: Path, password: str, every: int, dest_zip: Path) -> int:
    if every < 1:
        raise PdfError("Split size must be at least 1 page.")
    src = open_doc(path, password)
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    chunks = 0
    try:
        with zipfile.ZipFile(dest_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for start in range(0, src.page_count, every):
                end = min(start + every - 1, src.page_count - 1)
                one = fitz.open()
                one.insert_pdf(src, from_page=start, to_page=end)
                buf = one.tobytes(garbage=4, deflate=True)
                one.close()
                chunks += 1
                zf.writestr(f"part-{chunks:03d}_pages-{start + 1}-{end + 1}.pdf", buf)
        return chunks
    finally:
        src.close()


def reorder(path: Path, password: str, order: list[int], dest: Path) -> None:
    src = open_doc(path, password)
    try:
        if sorted(order) != list(range(src.page_count)):
            raise PdfError("Reorder must include every page exactly once.")
        extract_pages(path, password, order, dest)
    finally:
        src.close()


def drop_pages(path: Path, password: str, drop: list[int], dest: Path) -> None:
    src = open_doc(path, password)
    try:
        keep = [i for i in range(src.page_count) if i not in set(drop)]
        if not keep:
            raise PdfError("That would delete every page.")
        extract_pages(path, password, keep, dest)
    finally:
        src.close()


def rotate(path: Path, password: str, indexes: list[int], degrees: int, dest: Path) -> None:
    if degrees not in (90, 180, 270, -90):
        raise PdfError("Rotation must be 90, 180, or 270 degrees.")
    src = open_doc(path, password)
    try:
        for i in indexes:
            src[i].set_rotation((src[i].rotation + degrees) % 360)
        dest.parent.mkdir(parents=True, exist_ok=True)
        src.save(dest, garbage=4, deflate=True)
    finally:
        src.close()


def compress(path: Path, password: str, dest: Path) -> tuple[int, int]:
    src = open_doc(path, password)
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        src.save(dest, garbage=4, deflate=True, clean=True, deflate_images=True, deflate_fonts=True)
    finally:
        src.close()
    return path.stat().st_size, dest.stat().st_size


def watermark(path: Path, password: str, text: str, dest: Path) -> None:
    if not text.strip():
        raise PdfError("Enter watermark text.")
    src = open_doc(path, password)
    try:
        mark = text.strip()
        for page in src:
            rect = page.rect
            size = max(22, min(rect.width, rect.height) / 9)
            page.insert_textbox(
                fitz.Rect(36, rect.height * 0.34, rect.width - 36, rect.height * 0.66),
                mark,
                fontsize=size,
                fontname="hebo",
                color=(0.70, 0.66, 0.60),
                align=fitz.TEXT_ALIGN_CENTER,
                overlay=True,
            )
        dest.parent.mkdir(parents=True, exist_ok=True)
        src.save(dest, garbage=4, deflate=True)
    finally:
        src.close()


def extract_text(path: Path, password: str, dest: Path) -> int:
    src = open_doc(path, password)
    dest.parent.mkdir(parents=True, exist_ok=True)
    parts: list[str] = []
    try:
        for i, page in enumerate(src):
            parts.append(f"----- page {i + 1} -----\n{page.get_text('text').strip()}\n")
        dest.write_text("\n".join(parts), encoding="utf-8")
        return src.page_count
    finally:
        src.close()


def extract_images(path: Path, password: str, dest_zip: Path) -> int:
    src = open_doc(path, password)
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    try:
        with zipfile.ZipFile(dest_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for i, page in enumerate(src):
                for j, img in enumerate(page.get_images(full=True)):
                    xref = img[0]
                    try:
                        extracted = src.extract_image(xref)
                    except Exception:
                        continue
                    ext = extracted.get("ext") or "bin"
                    count += 1
                    zf.writestr(f"p{i + 1:04d}_img{j + 1:02d}.{ext}", extracted["image"])
        if count == 0:
            raise PdfError("No embedded images were found in this PDF.")
        return count
    finally:
        src.close()


def unlock(path: Path, password: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    last_error = None
    try:
        doc = open_doc(path, password)
        try:
            doc.save(dest, garbage=4, deflate=True, encryption=fitz.PDF_ENCRYPT_NONE)
            return
        finally:
            doc.close()
    except PdfError as exc:
        last_error = exc
    try:
        with pikepdf.open(path, password=password or "") as pdf:
            pdf.save(dest)
        return
    except pikepdf.PasswordError as exc:
        raise PdfError("The password did not unlock this PDF.") from exc
    except Exception as exc:
        if last_error:
            raise last_error from exc
        raise PdfError("Could not decrypt this PDF with the password given.") from exc


def lock(path: Path, password: str, new_password: str, dest: Path) -> None:
    if len(new_password) < 4:
        raise PdfError("Choose a password of at least 4 characters.")
    src = open_doc(path, password)
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        src.save(
            dest,
            garbage=4,
            deflate=True,
            encryption=fitz.PDF_ENCRYPT_AES_256,
            user_pw=new_password,
            owner_pw=new_password,
        )
    finally:
        src.close()


def set_metadata(path: Path, password: str, fields: dict, dest: Path) -> None:
    src = open_doc(path, password)
    try:
        meta = src.metadata or {}
        for key in ("title", "author", "subject", "keywords"):
            if key in fields and fields[key] is not None:
                meta[key] = str(fields[key])
        src.set_metadata(meta)
        dest.parent.mkdir(parents=True, exist_ok=True)
        src.save(dest, garbage=4, deflate=True)
    finally:
        src.close()
