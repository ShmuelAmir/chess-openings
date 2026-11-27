"""Fail when code or docs mention a Markdown doc that doesn't exist.

Scans tracked source and Markdown files for `*.md` paths (comments, docstrings,
inline code, links) and reports each one that resolves neither relative to the
mentioning file nor to the repo root. Run from anywhere inside the repo.
"""

import re
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

# Not preceded by a path or URL character, so `https://host/x/README.md` and
# `~/.claude/notes.md` are skipped: neither lives in this repo.
MD_PATH = re.compile(r"(?<![\w./:-])((?:[\w.-]+/)*[\w.-]*\w\.md)\b")

# Lockfiles and the like are skipped: they are data, not prose.
SCANNED_SUFFIXES = {
    ".md",
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".yml",
    ".yaml",
    ".html",
    ".toml",
}
SCANNED_NAMES = {"Makefile"}

# Docs that steering docs mention on purpose without them existing: the
# multi-context layout in docs/agents/domain.md applies only if one is added.
OPTIONAL_DOCS = {"GLOSSARY-MAP.md"}


class BrokenLink(NamedTuple):
    file: Path
    line: int
    target: str


def find_broken_links(root: Path, files: list[Path]) -> list[BrokenLink]:
    broken = []
    for path in files:
        rel = path.relative_to(root)
        in_fence = False
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            # Fenced blocks in Markdown hold example trees and snippets, not
            # references to this repo's docs.
            if path.suffix == ".md" and line.lstrip().startswith(("```", "~~~")):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            for match in MD_PATH.finditer(line):
                target = match.group(1)
                if target in OPTIONAL_DOCS:
                    continue
                if not (path.parent / target).exists() and not (root / target).exists():
                    broken.append(BrokenLink(rel, number, target))
    return broken


def tracked_files(root: Path) -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, capture_output=True, text=True, check=True
    ).stdout
    paths = (root / name for name in out.split("\0") if name)
    return [
        p
        for p in paths
        if (p.suffix in SCANNED_SUFFIXES or p.name in SCANNED_NAMES) and p.is_file()
    ]


def main() -> int:
    root = Path(
        subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    )
    broken = find_broken_links(root, tracked_files(root))
    for link in broken:
        print(
            f"{link.file}:{link.line}: {link.target} doesn't exist "
            "(relative to the file or the repo root)",
            file=sys.stderr,
        )
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
