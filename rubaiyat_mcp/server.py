"""MCP server for the Rubaiyat of Khayyam corpus.

Tools cover word frequency, n-grams, key-word-in-context concordance,
per-quatrain distribution, full-text search and quatrain lookup, over the
aligned English (FitzGerald) and Persian texts shipped in this repository.

Run with ``python -m rubaiyat_mcp`` (stdio transport, the default for
Claude Code / Claude Desktop) or ``rubaiyat-mcp --transport streamable-http``.
"""

from __future__ import annotations

import argparse
from typing import Literal

try:  # mcp >= 2.0
    from mcp.server.mcpserver import MCPServer
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as MCPServer  # type: ignore[no-redef]

from rubaiyat_mcp import __version__
from rubaiyat_mcp.corpus import LANGUAGES, Corpus, Language, Line, load_corpora, normalize

Scope = Literal["english", "persian", "both"]

INSTRUCTIONS = """\
Word-frequency and concordance tools for the Rubaiyat of Omar Khayyam.
Two aligned corpora are available: 'english' (Edward FitzGerald's translation)
and 'persian' (the original). Both hold 75 quatrains of four lines, and
quatrain N in one language corresponds to quatrain N in the other.
Words are matched after normalisation (English lower-cased; Persian with
Arabic yeh/kaf folded to Persian forms and diacritics removed), so either
spelling variant finds the same word.
"""

server = MCPServer(
    name="rubaiyat",
    title="Rubaiyat of Khayyam corpus",
    instructions=INSTRUCTIONS,
    version=__version__,
)

_corpora: dict[Language, Corpus] | None = None


def corpora() -> dict[Language, Corpus]:
    """Parse the XML files on first use and cache them for the process."""
    global _corpora
    if _corpora is None:
        _corpora = load_corpora()
    return _corpora


def corpus(language: Language) -> Corpus:
    try:
        return corpora()[language]
    except KeyError:
        raise ValueError(f"unknown language {language!r}; choose one of {', '.join(LANGUAGES)}") from None


def _scope(language: Scope) -> list[Language]:
    if language == "both":
        return list(LANGUAGES)
    return [language]


def _line(line: Line) -> dict:
    return {"quatrain": line.quatrain, "line": line.number, "text": line.text}


def _quatrain(c: Corpus, n: int) -> dict:
    return {
        "language": c.language,
        "quatrain": n,
        "lines": [line.text for line in c.quatrain(n)],
    }


# --------------------------------------------------------------------- tools


@server.tool()
def corpus_info() -> dict:
    """Describe the loaded corpora: files, quatrain/line counts, token and vocabulary sizes."""
    return {
        "corpora": [c.summary() for c in corpora().values()],
        "note": "Quatrain numbers are aligned between the English and Persian texts.",
    }


@server.tool()
def word_frequency(
    language: Language = "english",
    top_n: int = 50,
    min_length: int = 1,
    min_count: int = 1,
    exclude_stopwords: bool = False,
    starts_with: str | None = None,
    contains: str | None = None,
) -> dict:
    """Rank words in one language by how often they occur.

    Each row gives the raw count, the rate per 1000 tokens and the number of
    quatrains the word appears in. Set exclude_stopwords to drop function
    words (the, and, و, که ...). Use starts_with / contains to narrow the
    vocabulary, and top_n=0 to return every matching word.
    """
    c = corpus(language)
    rows = c.frequency(
        top_n=top_n or None,
        min_length=min_length,
        min_count=min_count,
        exclude_stopwords=exclude_stopwords,
        starts_with=starts_with,
        contains=contains,
    )
    return {
        "language": language,
        "total_tokens": c.total_tokens,
        "unique_words": len(c.term_counts),
        "returned": len(rows),
        "words": rows,
    }


@server.tool()
def ngram_frequency(
    language: Language = "english",
    n: int = 2,
    top_n: int = 30,
    exclude_stopwords: bool = False,
) -> dict:
    """Rank the most frequent word n-grams (bigrams by default) within lines of one language."""
    if n < 2 or n > 6:
        raise ValueError("n must be between 2 and 6")
    rows = corpus(language).ngrams(n, top_n=top_n or None, exclude_stopwords=exclude_stopwords)
    return {"language": language, "n": n, "returned": len(rows), "ngrams": rows}


@server.tool()
def word_context(
    word: str,
    language: Language = "english",
    max_results: int = 25,
    include_translation: bool = True,
) -> dict:
    """Show every line where a word occurs, with its full quatrain for context (a concordance).

    Matching is on whole normalised tokens, so 'wine' finds 'Wine' and 'WINE'
    but not 'winter'. With include_translation the aligned quatrain from the
    other language is attached to each hit.
    """
    c = corpus(language)
    other = corpora()["persian" if language == "english" else "english"]
    token = normalize(word, language).strip()
    occurrences = []
    for line in c.occurrences(word):
        entry = {
            **_line(line),
            "count_in_line": line.tokens.count(token),
            "quatrain_text": [ln.text for ln in c.quatrain(line.quatrain)],
        }
        if include_translation and line.quatrain in other.quatrains:
            entry["translation"] = {
                "language": other.language,
                "lines": [ln.text for ln in other.quatrain(line.quatrain)],
            }
        occurrences.append(entry)
    total = sum(e["count_in_line"] for e in occurrences)
    return {
        "word": word,
        "language": language,
        "total_count": total,
        "quatrains": sorted({e["quatrain"] for e in occurrences}),
        "returned": min(len(occurrences), max_results) if max_results else len(occurrences),
        "occurrences": occurrences[:max_results] if max_results else occurrences,
    }


@server.tool()
def word_distribution(word: str, language: Language = "english") -> dict:
    """Count a word's occurrences quatrain by quatrain, to see where in the poem it clusters."""
    c = corpus(language)
    dist = c.distribution(word)
    return {
        "word": word,
        "language": language,
        "total_count": sum(dist.values()),
        "quatrains_containing": len(dist),
        "by_quatrain": [{"quatrain": n, "count": k} for n, k in dist.items()],
    }


@server.tool()
def search_lines(
    query: str,
    language: Scope = "both",
    regex: bool = False,
    max_results: int = 50,
) -> dict:
    """Find lines containing a substring, or a regular expression when regex=true.

    Matching ignores case and Persian spelling variants (Arabic/Persian yeh and kaf).
    """
    results = {}
    for lang in _scope(language):
        hits = corpus(lang).search(query, regex=regex, max_results=max_results or None)
        results[lang] = [_line(h) for h in hits]
    return {"query": query, "regex": regex, "results": results}


@server.tool()
def get_quatrain(n: int, language: Scope = "both") -> dict:
    """Return quatrain n (1-75) in English, Persian, or both side by side."""
    out = {"quatrain": n}
    for lang in _scope(language):
        out[lang] = _quatrain(corpus(lang), n)["lines"]
    return out


@server.tool()
def compare_word_frequency(
    english_word: str,
    persian_word: str,
) -> dict:
    """Compare an English word with a Persian word: counts, and which quatrains contain each or both.

    Because quatrain numbers are aligned across the two texts, shared quatrains
    hint at where FitzGerald kept an image and where he departed from it.
    """
    en, fa = corpus("english"), corpus("persian")
    d_en, d_fa = en.distribution(english_word), fa.distribution(persian_word)
    return {
        "english": {"word": english_word, "count": sum(d_en.values()), "quatrains": list(d_en)},
        "persian": {"word": persian_word, "count": sum(d_fa.values()), "quatrains": list(d_fa)},
        "shared_quatrains": sorted(set(d_en) & set(d_fa)),
        "english_only_quatrains": sorted(set(d_en) - set(d_fa)),
        "persian_only_quatrains": sorted(set(d_fa) - set(d_en)),
    }


# ----------------------------------------------------------------- resources


@server.resource("rubaiyat://{language}/quatrain/{n}", mime_type="text/plain")
def quatrain_resource(language: str, n: int) -> str:
    """One quatrain as plain text, e.g. rubaiyat://english/quatrain/12."""
    return corpus(language).quatrain_text(n)  # type: ignore[arg-type]


@server.resource("rubaiyat://{language}/text", mime_type="text/plain")
def full_text_resource(language: str) -> str:
    """The whole poem in one language, quatrains separated by blank lines and numbered."""
    c = corpus(language)  # type: ignore[arg-type]
    return "\n\n".join(f"[{n}]\n{c.quatrain_text(n)}" for n in sorted(c.quatrains))


# ---------------------------------------------------------------- entrypoint


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="rubaiyat-mcp", description=__doc__)
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http", "sse"],
        default="stdio",
        help="MCP transport (default: stdio)",
    )
    args = parser.parse_args(argv)
    corpora()  # fail fast if the XML files are missing
    server.run(transport=args.transport)


if __name__ == "__main__":
    main()
