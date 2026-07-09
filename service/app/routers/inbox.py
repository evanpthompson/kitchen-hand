from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from markitdown import MarkItDown

from .. import core

router = APIRouter(prefix="/inbox", tags=["inbox"])

# Files small/text enough to inline in the API response.
TEXT_EXTENSIONS = {".txt", ".md", ".json"}


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
    caption: str | None = None,
    transcript: str | None = None,
    raw: str | None = None,
    meta: str | None = None,
    uploads: list[UploadFile] | None = None,
):
    """Manual capture for sources that stay paste/upload by design
    (Instagram, TikTok, documents, pasted text) — see docs/ingestion.md.
    """
    d = _slug_dir(slug, must_exist=False)
    d.mkdir(parents=True, exist_ok=True)

    written = []
    for field_name, content in [
        ("caption.txt", caption),
        ("transcript.txt", transcript),
        ("raw.txt", raw),
        ("meta.txt", meta),
    ]:
        if content is not None:
            (d / field_name).write_text(content)
            written.append(field_name)

    for upload in uploads or []:
        if not upload.filename:
            continue
        dest = d / upload.filename
        dest.write_bytes(await upload.read())
        written.append(upload.filename)

    if not written:
        raise HTTPException(400, "no content provided")

    return {"slug": slug, "captured_files": written}
