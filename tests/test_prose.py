"""The reading test, as a thing that runs rather than a number somebody quoted.

Section 13 asked whether every part of fileplan earns its cost, and one of the
costs is **the language**. John set the target on 2026-09-08: prose that reads
easily, with the lever named in his own analysis. The pieces already reading
well run about 14 words a sentence. The longest documents ran 23 to 26.
*"A sentence that holds three qualifications is teaching three things at once."*

On 2026-09-09 he decided what the read is: **words per sentence, per section,
at 15 or under**. Reading ease is reported beside it and does not decide.
Sentence length is the lever, and it is the half that survives vocabulary — a
section about the register carries long words at any sentence length, so an
ease floor there would penalise the subject rather than the writing. The read
is per section, so no dense section hides behind easy neighbours.

Until 13-8 every ease number quoted in this repo came from an uncommitted
heuristic. That is the shape `test_size.py` next door complains about in its
own first paragraph: a pair that could not be reproduced. So the reader ships,
and from here it is the number of record. Numbers written down before it
existed do not match it and were left as written, being dated records.

**It gates nothing.** No test here asserts any document's ease or words per
sentence. The suite grades that the reader works; a person reads the table:

    uv run python tests/test_prose.py docs/method.md

The pair with `test_size.py` is the point. That module measures the code, this
one measures the prose, and `test_docs.py` grades what the documents say.
"""

from __future__ import annotations

import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from test_docs import FENCED

#: A section shorter than this scores nothing and prints a dash. Reading ease
#: over a handful of words is arithmetic without a meaning: `## Verbs` is one
#: word and scores 121, `## Transitions` scores −48. A nonsense number that
#: looks ordinary is what the make-problems-visible rule refuses, so the reader
#: declines to produce one. The shape is `CEILING`'s, one module over.
MINIMUM_WORDS = 40

#: A word, hyphens and apostrophes joining rather than splitting: `sub-phase`
#: is one word to a reader and so is counted as one.
WORD = re.compile(r"[A-Za-z0-9_]+(?:[-'’][A-Za-z0-9_]+)*")

#: A sentence ends at terminal punctuation before whitespace or the end of the
#: text. `3.12` keeps its dot, because nothing follows it but a digit.
SENTENCE = re.compile(r"[.!?]+(?=\s|$)")

#: The three line shapes that begin a block: a heading, a list item, a table
#: row. A line before one of them ends whatever it was saying.
HEADING = re.compile(r"^\s{0,3}#{1,6}\s")
ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s")
ROW = re.compile(r"^\s*\|")

#: What is taken out before counting: a link's target but not its text, then
#: the marks that are punctuation for the eye rather than words on the page.
LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
MARKUP = re.compile(r"[`*>]|^\s{0,3}#{1,6}\s*|^\s*(?:[-*+]|\d+[.)])\s+")

VOWELS = "aeiouy"


@dataclass(frozen=True)
class Rating:
    """What one stretch of prose reads like."""

    ease: float
    wps: float
    words: int


def _syllables(word: str) -> int:
    """Vowel groups in *word*, silent trailing ``e`` dropped, never below one.

    The usual heuristic. It is wrong on a handful of words in any corpus and
    wrong the same way for every document it is pointed at, which is what a
    comparison needs.
    """
    word = word.lower().strip("'-")
    count = 0
    previous = False
    for character in word:
        vowel = character in VOWELS
        if vowel and not previous:
            count += 1
        previous = vowel
    if word.endswith("e") and count > 1 and not word.endswith(("le", "ee")):
        count -= 1
    return max(count, 1)


def _prepared(text: str) -> str:
    """*text* as sentences, with everything that is not prose taken out.

    Three of the reader's four decisions live here.

    **Every fenced block goes**, not only the transcripts. A TOML example is
    no more prose than a shell transcript is, and neither is read as sentences.
    `test_docs.py`'s `prose()` keeps a non-transcript fence, because it is
    building the *citation* haystack and this repo's own snippets really do
    name this repo's own sections. Different question, different answer. The
    regex is that module's `FENCED`, imported rather than written again: two
    fence parsers is the drift this repo refuses.

    **A block that ends without terminal punctuation ends a sentence anyway.**
    Twelve bullets with no full stops are twelve statements, not one 200-word
    sentence, and a paragraph introducing a fenced block with a colon does not
    run on into the paragraph after it. So a full stop goes in wherever a line
    is the last of its block — before a heading, a list item, a table row or a
    blank line, or at the end of the text.

    **Markdown is reduced**: a link's text survives and its target does not,
    and backticks, emphasis, quote marks, heading marks and list markers go.
    Left in, the URL of every cross-reference would count as words.
    """
    lines = FENCED.sub("", text).splitlines()

    def opens(index: int) -> bool:
        if index >= len(lines):
            return True
        line = lines[index]
        return not line.strip() or bool(
            HEADING.match(line) or ITEM.match(line) or ROW.match(line)
        )

    prepared = []
    for index, line in enumerate(lines):
        line = LINK.sub(r"\1", line)
        line = MARKUP.sub(" ", line).replace("|", " ")
        stripped = line.strip()
        if stripped and opens(index + 1) and not stripped.endswith((".", "!", "?")):
            stripped += "."
        prepared.append(stripped)
    return "\n".join(prepared)


def rate(text: str) -> Rating | None:
    """How *text* reads, or ``None`` if there is too little of it.

    Flesch reading ease, words per sentence and the word count. Under
    `MINIMUM_WORDS` the answer is no answer.
    """
    prepared = _prepared(text)
    words = WORD.findall(prepared)
    if len(words) < MINIMUM_WORDS:
        return None
    sentences = max(len(SENTENCE.findall(prepared)), 1)
    syllables = sum(_syllables(word) for word in words)
    wps = len(words) / sentences
    ease = 206.835 - 1.015 * wps - 84.6 * (syllables / len(words))
    return Rating(ease=ease, wps=wps, words=len(words))


@dataclass(frozen=True)
class Section:
    """One heading's span, and how it reads."""

    heading: str
    lines: int
    rating: Rating | None


def sections(text: str) -> list[Section]:
    """*text* split on every ATX heading, each span rated.

    A heading inside a fenced block is not a heading — the mask is `FENCED`
    again, so the splitter and the counter agree about where the fences are. A
    file with no headings comes back as one span named for the whole of it.
    """
    fenced = set()
    for block in FENCED.finditer(text):
        start = text.count("\n", 0, block.start())
        end = text.count("\n", 0, block.end())
        fenced.update(range(start, end + 1))

    lines = text.splitlines()
    spans: list[tuple[str, list[str]]] = [("(preamble)", [])]
    for index, line in enumerate(lines):
        if index not in fenced and HEADING.match(line):
            spans.append((line.lstrip("# ").strip(), [line]))
        else:
            spans[-1][1].append(line)
    if not spans[0][1]:
        spans.pop(0)
    return [
        Section(heading=heading, lines=len(body), rating=rate("\n".join(body)))
        for heading, body in spans
    ]


def test_the_reader_tells_plain_prose_from_dense_prose() -> None:
    """Without this the table could report one number forever.

    The two halves say the same thing with the same words. Only the sentence
    boundaries move, so words per sentence must move and reading ease with it.
    """
    words = (
        "The tool reads the plan file and it grades the item against it "
        "and it writes the head and it files the entry and it takes the "
        "claim and it leaves the cursor where the last session put it"
    )
    dense = f"{words} and {words}."
    plain = ". ".join(dense.split(" and ")) + "."

    assert rate(dense) is not None and rate(plain) is not None
    assert rate(dense).wps > 2 * rate(plain).wps
    assert rate(plain).ease > rate(dense).ease + 20


def test_the_fence_strip_actually_strips() -> None:
    """Without this the reader could score a transcript as prose.

    Both fences go, the transcript and the example, which is where this reader
    parts company with `test_docs.py`'s haystack.
    """
    body = "Run the verb and read what it says about the item it moved. " * 4
    fenced = (
        body
        + "\n\n```\n$ fileplan list --state plan --lacks claimed-by\n```\n\n"
        + "```toml\n[states.plan]\npath = \"plan\"\n```\n"
    )
    assert rate(fenced) == rate(body)
    assert "fileplan" not in _prepared(fenced)
    assert "states.plan" not in _prepared(fenced)


def _rated(name: str) -> str:
    """The text *name* is graded on: a module's docstring, or the whole file.

    A path ending in `.py` is read as its top-of-file docstring. Pointed at the
    file itself the reader counts the code as prose and reads a `# ---` banner
    as a heading, so the number it reports is the module's length rather than
    how the docstring reads. A module with no docstring reads as empty.
    """
    text = Path(name).read_text(encoding="utf-8")
    if name.endswith(".py"):
        return ast.get_docstring(ast.parse(text)) or ""
    return text


def test_a_python_path_is_read_as_its_module_docstring(tmp_path: Path) -> None:
    """Without this the reader could go back to scoring a module's code.

    A module docstring is prose a person reads and the code under it is not.
    Pointed at the file whole, the reader counted the code too and reported the
    module's length. So a `.py` path is read as its docstring and as nothing
    else, and the docstring carries no headings, which is one row in the table.
    """
    sentence = "The module holds the arithmetic and one read of the plan file."
    docstring = " ".join([sentence] * 5)
    module = tmp_path / "sample.py"
    module.write_text(
        f'"""{docstring}"""\n\n# --- the banner\nBUDGET = 5500\n\n\n'
        + 'def run(item: str) -> str:\n    """One sentence."""\n    return item\n',
        encoding="utf-8",
    )

    assert _rated(str(module)) == docstring
    assert rate(_rated(str(module))) == rate(docstring)
    assert len(sections(_rated(str(module)))) == 1


def _table(paths: list[str]) -> str:
    """The table the command prints: one row per section, one for the file.

    The whole-file row is dropped where the text is one section, a docstring
    being the case, since it would repeat the row above it exactly.
    """
    out = []
    for name in paths:
        text = _rated(name)
        out.append(f"\n{name}")
        out.append(f"{'section':<44}{'lines':>7}{'words':>8}{'wps':>8}{'ease':>8}")
        rows = sections(text)
        if len(rows) > 1:
            rows.append(Section("(whole file)", len(text.splitlines()), rate(text)))
        for row in rows:
            rating = row.rating
            scored = (
                f"{rating.words:>8}{rating.wps:>8.1f}{rating.ease:>8.1f}"
                if rating
                else f"{'-':>8}{'-':>8}{'-':>8}"
            )
            out.append(f"{row.heading[:43]:<44}{row.lines:>7}{scored}")
    return "\n".join(out)


if __name__ == "__main__":
    print(_table(sys.argv[1:]))
