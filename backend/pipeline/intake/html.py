"""Saved-page HTML parser (main document + optional ``*_files/`` sibling)."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

from backend.pipeline.models import ParseStatus
from backend.pipeline.redact import redact_url, require_salt

# Public library path markers — scripts matching these are listed but flagged.
_LIBRARY_MARKERS = (
    "jquery",
    "jsdelivr",
    "cdnjs",
    "unpkg.com",
    "googleapis.com/ajax",
    "googletagmanager",
    "fonts.googleapis",
    "fonts.gstatic",
    "bootstrap",
    "react.production",
    "react-dom.production",
)

_MIN_SKELETON_BYTES = 5 * 1024


@dataclass
class HtmlForm:
    action_redacted: str | None
    method: str
    field_names: list[str] = field(default_factory=list)


@dataclass
class HtmlAsset:
    kind: str  # "image" | "script" | "stylesheet"
    path_or_url_redacted: str
    is_library: bool = False
    local: bool = False


@dataclass
class HtmlParseResult:
    parse_status: ParseStatus
    error: str | None = None
    title: str | None = None
    visible_text: str = ""
    links: list[str] = field(default_factory=list)
    forms: list[HtmlForm] = field(default_factory=list)
    assets: list[HtmlAsset] = field(default_factory=list)
    dom_skeleton: str | None = None
    dom_skeleton_sha256: str | None = None
    main_bytes: int = 0
    files_dir: str | None = None


def parse_html(path: Path | str, *, salt: str | None = None) -> HtmlParseResult:
    """Parse a saved HTML page. Never raises for malformed input."""
    try:
        if salt is None:
            salt = require_salt()
        return _parse_html(Path(path), salt=salt)
    except Exception as exc:  # noqa: BLE001
        return HtmlParseResult(
            parse_status=ParseStatus.FAILED,
            error=_short_error(exc),
        )


def _parse_html(path: Path, *, salt: str) -> HtmlParseResult:
    if not path.is_file():
        return HtmlParseResult(parse_status=ParseStatus.FAILED, error="file not found")

    raw = path.read_bytes()
    main_bytes = len(raw)
    text = raw.decode("utf-8", errors="replace")

    parser = _PageParser()
    try:
        parser.feed(text)
        parser.close()
    except Exception as exc:  # noqa: BLE001
        return HtmlParseResult(
            parse_status=ParseStatus.PARTIAL,
            error=_short_error(exc),
            main_bytes=main_bytes,
            title=parser.title or None,
            visible_text=_normalize_ws(parser.visible_text),
        )

    base = f"file://{path.resolve().as_posix()}"
    links = [
        redact_url(urljoin(base, href), salt=salt)
        for href in parser.links
        if href and not href.startswith("#")
    ]
    forms = [
        HtmlForm(
            action_redacted=(
                redact_url(urljoin(base, form.action), salt=salt) if form.action else None
            ),
            method=(form.method or "get").lower(),
            field_names=list(form.fields),
        )
        for form in parser.forms
    ]

    files_dir = _sibling_files_dir(path)
    local_names = _list_local_files(files_dir) if files_dir else set()

    assets: list[HtmlAsset] = []
    for src in parser.images:
        resolved = urljoin(base, src)
        local = _is_local_ref(src, local_names)
        assets.append(
            HtmlAsset(
                kind="image",
                path_or_url_redacted=redact_url(resolved, salt=salt),
                local=local,
            )
        )
    for src in parser.scripts:
        resolved = urljoin(base, src)
        local = _is_local_ref(src, local_names)
        assets.append(
            HtmlAsset(
                kind="script",
                path_or_url_redacted=redact_url(resolved, salt=salt),
                is_library=_is_library(src),
                local=local,
            )
        )

    skeleton = None
    skeleton_hash = None
    if main_bytes >= _MIN_SKELETON_BYTES:
        skeleton = parser.skeleton
        skeleton_hash = hashlib.sha256(skeleton.encode("utf-8")).hexdigest()

    status = ParseStatus.OK
    if not parser.title and not parser.visible_text and not links:
        status = ParseStatus.PARTIAL

    return HtmlParseResult(
        parse_status=status,
        title=parser.title or None,
        visible_text=_normalize_ws(parser.visible_text),
        links=_dedupe(links),
        forms=forms,
        assets=assets,
        dom_skeleton=skeleton,
        dom_skeleton_sha256=skeleton_hash,
        main_bytes=main_bytes,
        files_dir=str(files_dir) if files_dir else None,
    )


class _FormState:
    def __init__(self) -> None:
        self.action: str | None = None
        self.method: str | None = None
        self.fields: list[str] = []


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self._in_title = False
        self._skip_depth = 0
        self.visible_parts: list[str] = []
        self.links: list[str] = []
        self.images: list[str] = []
        self.scripts: list[str] = []
        self.forms: list[_FormState] = []
        self._form: _FormState | None = None
        self._skeleton_parts: list[str] = []

    @property
    def visible_text(self) -> str:
        return " ".join(self.visible_parts)

    @property
    def skeleton(self) -> str:
        return "".join(self._skeleton_parts)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        ad = {k.lower(): (v or "") for k, v in attrs}
        tag_l = tag.lower()
        if tag_l in {"script", "style", "noscript"}:
            self._skip_depth += 1
            if tag_l == "script":
                src = ad.get("src")
                if src:
                    self.scripts.append(src)
            self._skeleton_parts.append(f"<{tag_l}>")
            return

        self._skeleton_parts.append(f"<{tag_l}>")

        if tag_l == "title":
            self._in_title = True
        elif tag_l == "a" and ad.get("href"):
            self.links.append(ad["href"])
        elif tag_l in {"img", "source"} and ad.get("src"):
            self.images.append(ad["src"])
        elif tag_l == "form":
            self._form = _FormState()
            self._form.action = ad.get("action") or None
            self._form.method = ad.get("method") or "get"
        elif tag_l in {"input", "select", "textarea"} and self._form is not None:
            name = ad.get("name")
            if name:
                self._form.fields.append(name)

    def handle_endtag(self, tag: str) -> None:
        tag_l = tag.lower()
        if tag_l in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
        if tag_l == "title":
            self._in_title = False
        if tag_l == "form" and self._form is not None:
            self.forms.append(self._form)
            self._form = None
        self._skeleton_parts.append(f"</{tag_l}>")

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        if self._skip_depth:
            return
        if data.strip():
            self.visible_parts.append(data.strip())


def _sibling_files_dir(html_path: Path) -> Path | None:
    stem = html_path.stem
    candidate = html_path.with_name(f"{stem}_files")
    if candidate.is_dir():
        return candidate
    # Chrome sometimes uses "foo_files" next to "foo.htm"
    alt = html_path.parent / f"{html_path.name}_files"
    if alt.is_dir():
        return alt
    return None


def _list_local_files(files_dir: Path) -> set[str]:
    names: set[str] = set()
    for p in files_dir.rglob("*"):
        if p.is_file():
            names.add(p.name.lower())
            names.add(p.relative_to(files_dir).as_posix().lower())
    return names


def _is_local_ref(ref: str, local_names: set[str]) -> bool:
    if not ref or ref.startswith(("http://", "https://", "data:", "//")):
        return False
    name = ref.split("?")[0].split("#")[0].replace("\\", "/").lower()
    base = name.rsplit("/", 1)[-1]
    return name in local_names or base in local_names


def _is_library(src: str) -> bool:
    low = src.lower()
    return any(marker in low for marker in _LIBRARY_MARKERS)


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _short_error(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"[:200]
