"""Every relative link in the Markdown docs points to a file or folder that exists."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = sorted(p for p in [*ROOT.glob("*.md"), *ROOT.glob("docs/**/*.md")] if "PLAN" not in p.name)
LINK = re.compile(r"\]\(([^)\s]+)\)")
FENCE = re.compile(r"^```.*?^```", re.S | re.M)


@pytest.mark.parametrize("path", DOCS, ids=lambda p: str(p.relative_to(ROOT)))
def test_relative_links_resolve(path: Path) -> None:
    text = FENCE.sub("", path.read_text())
    broken = []
    for target in LINK.findall(text):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        file = target.split("#")[0]
        if not (path.parent / file).resolve().exists():
            broken.append(target)
    assert not broken, broken
