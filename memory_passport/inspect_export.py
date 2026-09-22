"""``passport inspect``: report what an export contains before importing it.

Meant for the moment a product changes its format. It never writes anything and prints
counts rather than content, so the output is safe to paste into a bug report.
"""

from __future__ import annotations

import json
import zipfile
from collections import Counter
from pathlib import Path


def inspect_path(path: Path) -> list[str]:
    lines: list[str] = []
    names: list[str]
    reader = None
    if path.is_file() and path.suffix == ".zip":
        z = zipfile.ZipFile(path)
        names = z.namelist()
        reader = lambda n: z.read(n)  # noqa: E731
        lines.append(f"zip with {len(names)} member(s):")
    elif path.is_dir():
        names = [str(p.relative_to(path)) for p in sorted(path.rglob("*")) if p.is_file()]
        reader = lambda n: (path / n).read_bytes()  # noqa: E731
        lines.append(f"folder with {len(names)} file(s):")
    else:
        names = [path.name]
        reader = lambda n: path.read_bytes()  # noqa: E731
        lines.append("single file:")
    for n in names[:40]:
        lines.append(f"  {n}")
    if len(names) > 40:
        lines.append(f"  … and {len(names) - 40} more")

    for n in names:
        base = n.rsplit("/", 1)[-1]
        if base == "conversations.json":
            lines += _inspect_chatgpt_conversations(reader(n), n)
        elif base == "projects.json":
            lines += _inspect_claude_projects(reader(n), n)
        elif base == "MEMORY.md":
            lines.append(f"{n}: looks like a Claude Code memory index")
    return lines


def _inspect_chatgpt_conversations(raw: bytes, label: str) -> list[str]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return [f"{label}: not valid JSON ({e})"]
    if isinstance(data, dict):
        if "chat_messages" in data or "uuid" in data:
            return [f"{label}: looks like a claude.ai conversation, not ChatGPT"]
        data = [data]
    if not isinstance(data, list):
        return [f"{label}: unexpected top-level type {type(data).__name__}"]
    if data and isinstance(data[0], dict) and "chat_messages" in data[0]:
        n_msgs = sum(len(c.get("chat_messages") or []) for c in data)
        return [
            f"{label}: claude.ai export, {len(data)} conversation(s), {n_msgs} message(s); "
            "no memory inside"
        ]
    roles: Counter[str] = Counter()
    recipients: Counter[str] = Counter()
    ctypes: Counter[str] = Counter()
    tool_names: Counter[str] = Counter()
    bio = 0
    for conv in data:
        for node in (conv.get("mapping") or {}).values():
            msg = (node or {}).get("message") or {}
            if not msg:
                continue
            author = msg.get("author") or {}
            roles[str(author.get("role"))] += 1
            recipients[str(msg.get("recipient"))] += 1
            ctypes[str((msg.get("content") or {}).get("content_type"))] += 1
            if author.get("role") == "tool":
                tool_names[str(author.get("name"))] += 1
            if msg.get("recipient") == "bio" and author.get("role") == "assistant":
                bio += 1
    out = [f"{label}: ChatGPT export, {len(data)} conversation(s)"]
    out.append("  roles:      " + ", ".join(f"{k}={v}" for k, v in roles.most_common()))
    out.append("  recipients: " + ", ".join(f"{k}={v}" for k, v in recipients.most_common(8)))
    out.append("  content:    " + ", ".join(f"{k}={v}" for k, v in ctypes.most_common(8)))
    if tool_names:
        out.append("  tools:      " + ", ".join(f"{k}={v}" for k, v in tool_names.most_common(8)))
    out.append(f"  saved memories (assistant -> bio): {bio}")
    if bio == 0:
        out.append(
            "  no bio messages found. Either memory was off, or the format changed; "
            "please open an issue with this output."
        )
    return out


def _inspect_claude_projects(raw: bytes, label: str) -> list[str]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return [f"{label}: not valid JSON ({e})"]
    if not isinstance(data, list):
        return [f"{label}: unexpected top-level type {type(data).__name__}"]
    with_tpl = sum(
        1 for p in data if isinstance(p, dict) and (p.get("prompt_template") or "").strip()
    )
    keys: Counter[str] = Counter(k for p in data if isinstance(p, dict) for k in p)
    return [
        f"{label}: claude.ai export, {len(data)} project(s), {with_tpl} with instructions",
        "  keys: " + ", ".join(k for k, _ in keys.most_common(12)),
    ]
