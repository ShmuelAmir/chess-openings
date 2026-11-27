import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from check_md_links import BrokenLink, find_broken_links  # noqa: E402


def write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_a_comment_naming_a_missing_doc_is_reported_with_its_line(tmp_path):
    src = write(
        tmp_path, "backend/users.py", '"""Users.\n\nSee User in CONTEXT.md."""\n'
    )

    assert find_broken_links(tmp_path, [src]) == [
        BrokenLink(Path("backend/users.py"), 3, "CONTEXT.md")
    ]


def test_a_doc_resolves_relative_to_the_mentioning_file_or_the_repo_root(tmp_path):
    write(tmp_path, "GLOSSARY.md", "# Glossary\n")
    write(tmp_path, "docs/agents/triage-labels.md", "# Labels\n")
    doc = write(
        tmp_path,
        "docs/agents/issue-tracker.md",
        "See `triage-labels.md`, `GLOSSARY.md` and [it](../../GLOSSARY.md#sync).\n",
    )

    assert find_broken_links(tmp_path, [doc]) == []


def test_example_paths_in_a_markdown_code_fence_are_ignored(tmp_path):
    doc = write(
        tmp_path,
        "docs/agents/domain.md",
        "Layout:\n\n```\n/\n├── docs/adr/\n│   └── 0001-event-sourced-orders.md\n```\n\nSee `GONE.md`.\n",
    )

    assert find_broken_links(tmp_path, [doc]) == [
        BrokenLink(Path("docs/agents/domain.md"), 9, "GONE.md")
    ]


def test_urls_and_docs_that_are_optional_by_design_are_not_reported(tmp_path):
    doc = write(
        tmp_path,
        "docs/agents/domain.md",
        "See https://github.com/org/repo/blob/main/README.md.\n"
        "Read `GLOSSARY-MAP.md` at the repo root if it exists.\n",
    )

    assert find_broken_links(tmp_path, [doc]) == []


SCRIPT = Path(__file__).resolve().parents[1] / "check_md_links.py"


def run_check(repo: Path) -> subprocess.CompletedProcess:
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    return subprocess.run(
        [sys.executable, str(SCRIPT)], cwd=repo, capture_output=True, text=True
    )


def test_the_check_fails_naming_file_and_line_of_a_missing_doc(tmp_path):
    write(tmp_path, "GLOSSARY.md", "# Glossary\n")
    write(tmp_path, "frontend/src/Panel.jsx", "/**\n * See Sync in CONTEXT.md.\n */\n")

    result = run_check(tmp_path)

    assert result.returncode == 1
    assert "frontend/src/Panel.jsx:2: CONTEXT.md" in result.stderr


def test_the_check_passes_when_every_mentioned_doc_exists(tmp_path):
    write(tmp_path, "GLOSSARY.md", "# Glossary\n")
    write(tmp_path, "backend/users.py", '"""See User in GLOSSARY.md."""\n')

    result = run_check(tmp_path)

    assert result.returncode == 0, result.stderr


def test_a_fence_closes_only_on_its_own_marker(tmp_path):
    doc = write(
        tmp_path,
        "README.md",
        "```markdown\n~~~\nexample.md\n```\n\nSee `GONE.md`.\n",
    )

    assert find_broken_links(tmp_path, [doc]) == [
        BrokenLink(Path("README.md"), 6, "GONE.md")
    ]
