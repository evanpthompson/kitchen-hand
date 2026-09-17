from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, UploadFile
from markitdown import MarkItDown

from .. import core

router = APIRouter(prefix="/inbox", tags=["inbox"])

# Files small/text enough to inline in the API response.
TEXT_EXTENSIONS = {".txt", ".md", ".json"}

# Allow-list of what an upload may be, by extension. A capture is a photo of a
# recipe card, a screenshot of a carousel post, or a document — nothing else
# belongs in inbox/, and an allow-list refuses the file type nobody has thought
# of yet, which a deny-list cannot.
UPLOAD_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".heic",
    ".pdf",
    ".txt",
    ".md",
    ".json",
}


def _slug_dir(slug: str, must_exist: bool) -> Path:
    if not core.is_valid_slug(slug):
        raise HTTPException(400, f"invalid slug: {slug}")
    d = core.INBOX_DIR / slug
    if must_exist and not d.is_dir():
        raise HTTPException(404, f"no inbox folder for slug: {slug}")
    return d


@router.get("")
def list_inbox():
    if not core.INBOX_DIR.is_dir():
        return []
    out = []
    for d in sorted(core.INBOX_DIR.iterdir()):
        if not d.is_dir():
            continue
        files = [f.name for f in d.iterdir() if f.is_file()]
        out.append(
            {
                "slug": d.name,
                "files": sorted(files),
                "source_type_guess": core.infer_inbox_source_type(files),
                "has_draft": (core.DRAFTS_DIR / f"{d.name}.yaml").exists(),
                "captured_at": max(
                    (f.stat().st_mtime for f in d.iterdir() if f.is_file()),
                    default=None,
                ),
            }
        )
    return out


@router.get("/{slug}")
def get_inbox_capture(slug: str):
    d = _slug_dir(slug, must_exist=True)
    files = []
    for f in sorted(d.iterdir()):
        if not f.is_file():
            continue
        entry = {"name": f.name, "size": f.stat().st_size}
        if f.suffix in TEXT_EXTENSIONS:
            entry["content"] = f.read_text(errors="replace")
        else:
            entry["content"] = None  # fetch raw bytes via GET /inbox/{slug}/files/{name}
        files.append(entry)
    return {"slug": slug, "files": files}


@router.get("/{slug}/files/{filename}")
def get_inbox_file_raw(slug: str, filename: str):
    d = _slug_dir(slug, must_exist=True)
    path = d / filename
    if not path.is_file() or path.parent != d:
        raise HTTPException(404, "file not found")
    from fastapi.responses import FileResponse

    return FileResponse(path)


@router.post("/{slug}/youtube")
def capture_youtube(slug: str, body: dict):
    url = body.get("url")
    if not url:
        raise HTTPException(400, "body must include 'url'")

    d = _slug_dir(slug, must_exist=False)
    d.mkdir(parents=True, exist_ok=True)

    result = MarkItDown().convert(url)
    (d / "youtube.md").write_text(result.markdown)
    (d / "url.txt").write_text(url + "\n")

    return {"slug": slug, "captured_files": ["youtube.md", "url.txt"]}


@router.post("/{slug}/files")
async def capture_files(
    slug: str,
    caption: Annotated[str | None, Form()] = None,
    transcript: Annotated[str | None, Form()] = None,
    raw: Annotated[str | None, Form()] = None,
    meta: Annotated[str | None, Form()] = None,
    uploads: list[UploadFile] | None = None,
):
    """Manual capture for sources that stay paste/upload by design
    (Instagram, TikTok, documents, pasted text) — see docs/ingestion.md.

    The text fields are multipart form fields, not query parameters: a recipe
    caption runs to several paragraphs and does not fit in a URL.

    Blank content is treated as "not provided" and leaves the file on disk
    alone. That matters because tools/import_instagram_saved.py writes meta.txt
    ahead of the paste, and a capture screen that failed to load it would
    otherwise post an empty box over the handle and permalink.
    """
    d = _slug_dir(slug, must_exist=False)

    text_files = [
        ("caption.txt", caption),
        ("transcript.txt", transcript),
        ("raw.txt", raw),
        ("meta.txt", meta),
    ]
    incoming = [(n, c) for n, c in text_files if c is not None and c.strip()]
    safe_uploads = [_safe_upload_name(u) for u in (uploads or []) if u.filename]

    if not incoming and not safe_uploads:
        raise HTTPException(400, "no content provided")

    d.mkdir(parents=True, exist_ok=True)
    written = []
    for name, content in incoming:
        (d / name).write_text(content)
        written.append(name)

    for upload, name in zip(uploads or [], [n for n in safe_uploads]):
        (d / name).write_bytes(await upload.read())
        written.append(name)

    return {"slug": slug, "captured_files": written}


def _safe_upload_name(upload: UploadFile) -> str:
    """Reduce a client-supplied filename to a basename on the allow-list.

    Without this, an upload named ../../recipes/kung-pao-chicken.yaml would
    write straight through the trusted collection — the capture folder is
    chosen by the server, so the filename must never be able to leave it.
    """
    name = Path(upload.filename or "").name
    if not name or name.startswith("."):
        raise HTTPException(400, f"unusable upload filename: {upload.filename!r}")
    if Path(name).suffix.lower() not in UPLOAD_EXTENSIONS:
        raise HTTPException(
            400,
            f"upload type not allowed: {name!r}. Allowed: {', '.join(sorted(UPLOAD_EXTENSIONS))}",
        )
    return name
