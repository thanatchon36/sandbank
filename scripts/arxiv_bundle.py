"""Build the arXiv source bundle, ``paper/arxiv.tar.gz``, from the paper as last built.

arXiv compiles the paper itself, from the root of the bundle, with XeLaTeX (declared in
``00README.json``). This stages ``main.tex`` with the figures moved inside the bundle, the
section files, ``numbers.tex``, the generated tables and appendix texts, ``refs.bib`` and a
precompiled ``main.bbl``; compiles the staged copy once with tectonic to prove it is
self-contained; then tars it. It also prints the title, the plain-text abstract (for the
arXiv form) and a comments line. Run ``make paper`` first.

Usage: ``python scripts/arxiv_bundle.py``.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "paper"
STAGE = PAPER / "arxiv"
OUT = PAPER / "arxiv.tar.gz"
FIGURES = ROOT / "figures" / "out"
INTERMEDIATES = ("main.aux", "main.log", "main.out", "main.blg", "main.pdf")


def plain_abstract() -> str:
    """The abstract as plain text with ``numbers.tex`` macros filled in."""
    defs = (PAPER / "numbers.tex").read_text(encoding="utf-8")
    macros = dict(re.findall(r"^\\newcommand\{\\([A-Za-z]+)\}\{(.*)\}$", defs, re.M))
    text = (PAPER / "sections" / "abstract.tex").read_text(encoding="utf-8")
    text = re.sub(r"(?<!\\)%.*", "", text)
    text = re.sub(r"\\([A-Za-z]+)(\{\})?", lambda m: macros.get(m.group(1), m.group(0)), text)
    for a, b in (("{,}", ","), ("\\%", "%"), ("~", " "), ("``", '"'), ("''", '"'), ("---", "-"), ("--", "-")):
        text = text.replace(a, b)
    return " ".join(text.split())


def main() -> int:
    if STAGE.exists():
        shutil.rmtree(STAGE)
    (STAGE / "figures").mkdir(parents=True)
    main_tex = (PAPER / "main.tex").read_text(encoding="utf-8")
    if "\\graphicspath{{../figures/out/}}" not in main_tex:
        raise SystemExit("main.tex: expected \\graphicspath{{../figures/out/}}")
    (STAGE / "main.tex").write_text(
        main_tex.replace("\\graphicspath{{../figures/out/}}", "\\graphicspath{{figures/}}"),
        encoding="utf-8",
    )
    for name in ("numbers.tex", "refs.bib", "00README.json"):
        shutil.copyfile(PAPER / name, STAGE / name)
    for sub in ("sections", "generated"):
        shutil.copytree(PAPER / sub, STAGE / sub)
    sections = "".join(p.read_text(encoding="utf-8") for p in (PAPER / "sections").glob("*.tex"))
    figures = sorted(set(re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([\w-]+\.pdf)\}", sections)))
    for name in figures:
        shutil.copyfile(FIGURES / name, STAGE / "figures" / name)
    # the staged copy must compile on its own; this also writes main.bbl
    subprocess.run(
        ["tectonic", "-X", "compile", "--keep-intermediates", "--keep-logs", "main.tex"],
        cwd=STAGE,
        check=True,
        capture_output=True,
    )
    log = (STAGE / "main.log").read_text(encoding="utf-8", errors="replace")
    pages = re.search(r"Output written on main\.(?:xdv|pdf) \((\d+) pages", log)
    if pages is None or not (STAGE / "main.bbl").exists():
        raise SystemExit("staged compile left no page count or no main.bbl")
    for name in INTERMEDIATES:
        (STAGE / name).unlink(missing_ok=True)
    with tarfile.open(OUT, "w:gz") as tar:
        for p in sorted(STAGE.rglob("*")):
            if p.is_file():
                tar.add(p, arcname=str(p.relative_to(STAGE)))
    files = sorted(str(p.relative_to(STAGE)) for p in STAGE.rglob("*") if p.is_file())
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} kB, {len(files)} files)")
    print("\n".join(f"  {f}" for f in files))

    title = re.search(r"\\title\{(.*?)\\\\\[", main_tex, re.S)
    if title is None:
        raise SystemExit("main.tex: no \\title")
    body = plain_abstract()
    print(f"\nTitle:\n{' '.join(title.group(1).replace(chr(92) * 2, ' ').split())}")
    print(f"\nAbstract ({len(body)} characters; arXiv allows 1,920):\n{body}")
    print(
        f"\nComments:\n{pages.group(1)} pages, {len(figures)} figures. Pre-registered; code, data and "
        "the sandbox: https://github.com/thanatchon36/sandbank"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
