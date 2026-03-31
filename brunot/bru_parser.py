from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from .model import Request


SECTION_META = "meta"
SECTION_HEADERS = "headers"
SECTION_QUERY = "query"


def load_request_from_file(path: Path) -> Request:
    text = path.read_text(encoding="utf-8")
    return parse_bru(text, path)


def save_request_to_file(request: Request) -> None:
    if request.path is None:
        raise ValueError("Request.path is not set")
    request.path.parent.mkdir(parents=True, exist_ok=True)
    text = to_bru(request)
    request.path.write_text(text, encoding="utf-8")
    request.dirty = False


def parse_bru(text: str, path: Optional[Path] = None) -> Request:
    lines = [ln.rstrip("\n") for ln in text.splitlines()]
    section: Optional[str] = None
    meta: Dict[str, str] = {}
    headers: Dict[str, str] = {}
    query: Dict[str, str] = {}
    body_lines: List[str] = []

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        if line.endswith("{"):
            name = line.split("{", 1)[0].strip()
            section = name
            i += 1
            continue
        if line == "}":
            section = None
            i += 1
            continue

        if line.startswith("body:"):
            # body: | or inline; for MVP treat the rest as body
            content = line[len("body:") :].lstrip()
            if content == "|":
                i += 1
                while i < len(lines):
                    body_lines.append(lines[i])
                    i += 1
            else:
                body_lines.append(content)
            break

        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if section == SECTION_META:
                meta[key] = value
            elif section == SECTION_HEADERS:
                headers[key] = value
            elif section == SECTION_QUERY:
                query[key] = value
            # unknown sections are ignored for forward-compatibility

        i += 1

    name = meta.get("name", path.stem if path else "Request")
    method = meta.get("method", "GET")
    url = meta.get("url", "")

    return Request(
        name=name,
        method=method,
        url=url,
        headers=headers,
        query=query,
        body="\n".join(body_lines) if body_lines else None,
        path=path,
    )


def to_bru(request: Request) -> str:
    lines: List[str] = []

    lines.append("meta {")
    lines.append(f"  name: {request.name}")
    lines.append(f"  method: {request.method}")
    lines.append(f"  url: {request.url}")
    lines.append("}")

    if request.headers:
        lines.append("")
        lines.append("headers {")
        for k, v in request.headers.items():
            lines.append(f"  {k}: {v}")
        lines.append("}")

    if request.query:
        lines.append("")
        lines.append("query {")
        for k, v in request.query.items():
            lines.append(f"  {k}: {v}")
        lines.append("}")

    if request.body:
        lines.append("")
        lines.append("body: |")
        for ln in request.body.splitlines():
            lines.append(ln)

    lines.append("")
    return "\n".join(lines)

