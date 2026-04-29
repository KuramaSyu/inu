#!/usr/bin/env python3
"""Refactor top-level `core`, `utils`, `ext` imports to `inu.core`, `inu.utils`, `inu.ext`.

Usage: run from repo root. It edits .py files in-place and skips venv and the shim packages.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDE = {"venv", "test-venv", ".git", "core", "utils", "ext"}

all_py = list(ROOT.rglob("*.py"))
py_files = []
for p in all_py:
    try:
        first = p.relative_to(ROOT).parts[0]
    except Exception:
        continue
    if first in EXCLUDE:
        continue
    py_files.append(p)

patterns = [
    (re.compile(r"^(\s*from\s+)core(\b)"), r"\1inu.core"),
    (re.compile(r"^(\s*from\s+)utils(\b)"), r"\1inu.utils"),
    (re.compile(r"^(\s*from\s+)ext(\b)"), r"\1inu.ext"),
    (re.compile(r"^(\s*import\s+)core(\b)"), r"\1inu.core as core"),
    (re.compile(r"^(\s*import\s+)utils(\b)"), r"\1inu.utils as utils"),
    (re.compile(r"^(\s*import\s+)ext(\b)"), r"\1inu.ext as ext"),
]

changed = []
for p in py_files:
    text = p.read_text(encoding="utf-8")
    original = text
    lines = text.splitlines(True)
    new_lines = []
    for ln in lines:
        new_ln = ln
        for pat, repl in patterns:
            new_ln = pat.sub(repl, new_ln)
        new_lines.append(new_ln)
    new_text = "".join(new_lines)
    if new_text != original:
        p.write_text(new_text, encoding="utf-8")
        changed.append(str(p.relative_to(ROOT)))

print(f"Updated {len(changed)} files")
for f in changed:
    print(f)
