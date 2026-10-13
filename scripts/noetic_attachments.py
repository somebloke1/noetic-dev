"""Attachment transport validation, planning and storage for developer sessions.

Pure helpers: no session, native, provider or network effects. Callers translate
AttachmentError into their own transport error so this module imports nothing
from the session pipeline.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import re
import struct
from pathlib import Path

from scripts.noetic_storage import ensure_private_directory, open_private

PROTOCOL = "noetic-attachments-v1"
MAX_ATTACHMENTS = 8
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 4 * 1024 * 1024
MAX_FRAME_BYTES = 6 * 1024 * 1024
# Bound the encoded form before any decode/allocation: ceil(n/3)*4 characters.
MAX_ENCODED_CHARS = (MAX_FILE_BYTES + 2) // 3 * 4 + 4
FORBIDDEN_NAME_CHARACTERS = "\"'<>\\"
IMAGE_MIME_EXTENSIONS = {
    "image/png": (".png",),
    "image/jpeg": (".jpg", ".jpeg"),
    "image/gif": (".gif",),
    "image/webp": (".webp",),
    "image/bmp": (".bmp",),
}
TEXT_MIME_TYPES = {"application/json", "application/yaml", "application/x-yaml",
                   "application/xml", "application/javascript", "application/x-sh", "application/toml"}
TEXT_EXTENSIONS = {".md", ".markdown", ".txt", ".text", ".json", ".csv", ".tsv", ".yaml", ".yml",
                   ".xml", ".html", ".htm", ".css", ".js", ".mjs", ".ts", ".tsx", ".jsx", ".py",
                   ".sh", ".toml", ".ini", ".cfg", ".log", ".sql", ".rs", ".go", ".c", ".h",
                   ".cpp", ".hpp", ".java", ".rb", ".php", ".diff", ".patch"}
MIME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]{0,126}/[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]{0,126}$")
DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
EXTENSION_PATTERN = re.compile(r"^[.][A-Za-z0-9]{1,10}$")


class AttachmentError(ValueError):
    """Client-supplied attachment transport is malformed or unsupported."""


def _fail(message: str) -> None:
    raise AttachmentError(message)


def _prepare_item(item) -> dict:
    if not isinstance(item, dict):
        _fail("Each attachment must be an object with name, mime_type and data.")
    # Client input accepts EXACTLY name, mime_type, data and optional sha256.
    # Any kind/text/size/path/identity field is rejected, never stripped or ignored.
    if set(item) - {"name", "mime_type", "data", "sha256"}:
        _fail("Attachment objects accept exactly name, mime_type, optional sha256 and base64 data; no paths, identities or display metadata.")
    name, mime, data = item.get("name"), item.get("mime_type"), item.get("data")
    if not isinstance(name, str) or not name or len(name) > 255 or name.startswith(".") or name in (".", ".."):
        _fail("Attachment name must be a nonempty file name without a leading dot.")
    if any(character in name for character in "/\\" + FORBIDDEN_NAME_CHARACTERS) or any(
            ord(character) < 32 or ord(character) == 127 for character in name):
        _fail(f"Attachment name {name!r} must be one plain file name without traversal or control characters.")
    suffix = Path(name).suffix
    if not EXTENSION_PATTERN.fullmatch(suffix or ""):
        _fail(f"Attachment name {name!r} needs a plain file extension consistent with its MIME type.")
    if not isinstance(mime, str) or not MIME_PATTERN.fullmatch(mime):
        _fail(f"Attachment {name!r} needs a concrete mime_type such as image/png or text/markdown.")
    mime_lower = mime.lower()
    if not isinstance(data, str) or not data:
        _fail(f"Attachment {name!r} needs nonempty base64 data.")
    if len(data) > MAX_ENCODED_CHARS:
        _fail(f"Attachment {name!r} exceeds the {MAX_FILE_BYTES} byte decoded limit.")
    try:
        raw = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError):
        _fail(f"Attachment {name!r} data is not valid strict base64.")
    if not raw:
        _fail(f"Attachment {name!r} is empty.")
    if len(raw) > MAX_FILE_BYTES:
        _fail(f"Attachment {name!r} exceeds the {MAX_FILE_BYTES} byte decoded limit.")
    digest = hashlib.sha256(raw).hexdigest()
    supplied = item.get("sha256")
    if supplied is not None:
        if not isinstance(supplied, str) or not DIGEST_PATTERN.fullmatch(supplied):
            _fail(f"Attachment {name!r} sha256 must be an exact lowercase 64-character hex digest.")
        if supplied != digest:
            _fail(f"Attachment {name!r} sha256 does not match the decoded bytes.")
    prepared = {"name": name, "mime_type": mime_lower, "kind": "file",
                "data": base64.b64encode(raw).decode("ascii"), "sha256": digest, "size": len(raw)}
    if mime_lower.startswith("image/"):
        if mime_lower not in IMAGE_MIME_EXTENSIONS:
            _fail(f"Attachment {name!r} uses unsupported image type {mime}; supported native raster types are PNG, JPEG, GIF, WEBP and BMP.")
        if suffix.lower() not in IMAGE_MIME_EXTENSIONS[mime_lower]:
            _fail(f"Attachment {name!r} extension does not match its {mime_lower} type.")
        _verify_image(mime_lower, raw, name)
        prepared["kind"] = "image"
    elif mime_lower.startswith("text/") or mime_lower in TEXT_MIME_TYPES or suffix.lower() in TEXT_EXTENSIONS:
        try:
            prepared["text"] = raw.decode("utf-8")
        except UnicodeDecodeError:
            _fail(f"Attachment {name!r} declares textual content but is not valid UTF-8.")
        prepared["kind"] = "text"
    return prepared


def _verify_image(mime: str, raw: bytes, name: str) -> None:
    """Check actual complete-format structure, not a magic prefix alone."""
    if mime == "image/png":
        _verify_png(raw, name)
    elif mime == "image/jpeg":
        if not (raw.startswith(b"\xff\xd8\xff") and raw.endswith(b"\xff\xd9") and len(raw) >= 125):
            _fail(f"Attachment {name!r} is not a complete JPEG image.")
    elif mime == "image/gif":
        if not (raw[:6] in (b"GIF87a", b"GIF89a") and raw.endswith(b"\x3b") and len(raw) >= 13):
            _fail(f"Attachment {name!r} is not a complete GIF image.")
    elif mime == "image/webp":
        size = struct.unpack("<I", raw[4:8])[0] if len(raw) >= 12 else 0
        if not (len(raw) >= 30 and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP" and 18 <= size <= len(raw) - 8):
            _fail(f"Attachment {name!r} is not a complete WebP image.")
    elif mime == "image/bmp":
        declared = struct.unpack("<I", raw[2:6])[0] if len(raw) >= 6 else 0
        if not (raw[:2] == b"BM" and len(raw) >= 54 and 54 <= declared <= len(raw)):
            _fail(f"Attachment {name!r} is not a complete BMP image.")


def prepare(value):
    """Validate and canonicalize a client attachment list; [] behaves as plain text."""
    if value is None:
        _fail("Attachments must be a list when present; omit the field to send none.")
    if not isinstance(value, list):
        _fail("Attachments must be a list of file objects.")
    if len(value) > MAX_ATTACHMENTS:
        _fail(f"At most {MAX_ATTACHMENTS} attachments are accepted per message.")
    prepared, total = [], 0
    for item in value:
        entry = _prepare_item(item)
        total += entry["size"]
        if total > MAX_TOTAL_BYTES:
            _fail(f"Attachments exceed the {MAX_TOTAL_BYTES} byte total decoded limit.")
        prepared.append(entry)
    return prepared


def _verify_png(raw: bytes, name: str) -> None:
    """Bounded PNG chunk walk: signature, first IHDR(13) with nonzero dimensions,
    CRC32 per chunk, at least one IDAT, final zero-length IEND at exact end;
    acTL anywhere means animated PNG, which is unsupported."""
    if not raw.startswith(b"\x89PNG\r\n\x1a\n") or len(raw) < 57:
        _fail(f"Attachment {name!r} is not a complete non-animated PNG image.")
    offset, seen_ihdr, seen_idat = 8, False, False
    while offset + 12 <= len(raw):
        length = struct.unpack(">I", raw[offset:offset + 4])[0]
        kind = raw[offset + 4:offset + 8]
        end = offset + 12 + length
        if end > len(raw):
            _fail(f"Attachment {name!r} is not a complete PNG image (truncated {kind!r} chunk).")
        data = raw[offset + 8:offset + 8 + length]
        crc = struct.unpack(">I", raw[offset + 8 + length:end])[0]
        if crc != binascii.crc32(kind + data) & 0xFFFFFFFF:
            _fail(f"Attachment {name!r} has a corrupt PNG chunk {kind!r}.")
        if offset == 8:
            if kind != b"IHDR" or length != 13:
                _fail(f"Attachment {name!r} does not start with a 13-byte PNG IHDR chunk.")
            width, height = struct.unpack(">II", data[:8])
            if width == 0 or height == 0:
                _fail(f"Attachment {name!r} declares a zero-dimension PNG.")
            seen_ihdr = True
        elif kind == b"acTL":
            _fail(f"Attachment {name!r} is an animated PNG; only non-animated PNG is supported.")
        elif kind == b"IDAT":
            seen_idat = True
        elif kind == b"IEND":
            if not seen_ihdr or not seen_idat or length != 0 or end != len(raw):
                _fail(f"Attachment {name!r} is not a complete non-animated PNG image.")
            return
        offset = end
    _fail(f"Attachment {name!r} is not a complete PNG image (no IEND chunk).")


def canonical(prepared):
    """Exact wire payload {name, mime_type, data, sha256}; rich fields never cross a bound."""
    return [{"name": item["name"], "mime_type": item["mime_type"],
             "data": item["data"], "sha256": item["sha256"]} for item in prepared]


def plan(directory, prepared):
    """PURE deterministic owned paths and manifests for non-image attachments; no mkdir."""
    target = Path(directory) / "attachments"
    manifests = []
    for item in prepared:
        if item["kind"] == "image":
            continue
        stem = re.sub(r"[^A-Za-z0-9._-]", "_", Path(item["name"]).stem)[:64] or "attachment"
        path = target / f"{stem}.{item['sha256'][:16]}{Path(item['name']).suffix}"
        manifests.append({"name": item["name"], "mime_type": item["mime_type"], "size": item["size"],
                          "sha256": item["sha256"], "path": str(path), "source_id": f"sha256:{item['sha256']}"})
    return manifests


def write(manifests, prepared) -> None:
    """Create the owned directory and persist exact original bytes; called only after every refusal."""
    items = [item for item in prepared if item["kind"] != "image"]
    for item, manifest in zip(items, manifests):
        path = Path(manifest["path"])
        ensure_private_directory(path.parent)
        with open_private(path, "wb") as stream:
            stream.write(base64.b64decode(item["data"]))


def build_message(message: str, prepared, manifests) -> str:
    """Original human message retained exactly as the prefix, then bounded attachment content."""
    lines = [message]
    index = 0
    for item in prepared:
        if item["kind"] == "image":
            continue
        manifest = manifests[index]
        index += 1
        manifest_line = (f"Attachment manifest: name={item['name']}, mime_type={item['mime_type']}, "
                         f"bytes={item['size']}, sha256={item['sha256']}, path={manifest['path']}, "
                         f"source_id={manifest['source_id']}")
        if item["kind"] == "text":
            lines.append(f'<file name="{item["name"]}">\n{item["text"]}\n</file>')
        else:
            manifest_line += (" The exact retained bytes stay available at the recorded path for owned tool "
                              "access; the content has not been extracted, decoded, or read.")
        lines.append(manifest_line)
    return "\n".join(lines)
