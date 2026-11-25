"""MCP server for finding and quoting quatrains from the Rubaiyat of Khayyam.

The server exposes the two aligned texts in this repository, Edward
FitzGerald's English translation and the Persian original, so an assistant
can look up a quatrain by number, find quatrains by keyword or theme, pick
one at random, and get the text back formatted with attribution for use in
documents, slides, web pages and other artifacts.

Run with ``python -m rubaiyat_mcp`` (stdio transport, the default for
Claude Code / Claude Desktop) or ``rubaiyat-mcp --transport streamable-http``.
"""

from __future__ import annotations

import argparse
import random
from typing import Literal

try:  # mcp >= 2.0
    from mcp.server.mcpserver import MCPServer
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as MCPServer  # type: ignore[no-redef]

from rubaiyat_mcp import __version__
from rubaiyat_mcp.corpus import LANGUAGES, Corpus, Language, load_corpora
from rubaiyat_mcp.themes import THEMES, theme_words

Scope = Literal["english", "persian", "both"]
Format = Literal["json", "plain", "markdown", "html"]

ATTRIBUTION = {
    "english": "Omar Khayyam, translated by Edward FitzGerald",
    "persian": "عمر خیام",
}

INSTRUCTIONS = """\
Look up and quote quatrains (rubaiyat) of Omar Khayyam. Two aligned texts are
available: 'english' (Edward FitzGerald's translation) and 'persian' (the
original). Each has 75 four-line quatrains, and quatrain N in one language is
the counterpart of quatrain N in the other.

Typical flow: use find_quatrains with a keyword or a theme (see list_themes)
to shortlist candidates, then get_quatrain with format='markdown' or 'html'
to obtain quote-ready text with attribution for an artifact. random_quatrain
gives a quick epigraph. Matching ignores case and Persian spelling variants.
"""

server = MCPServer(
    name="rubaiyat",
    title="Rubaiyat of Khayyam",
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


def corpus(language: str) -> Corpus:
    try:
        return corpora()[language]  # type: ignore[index]
    except KeyError:
        raise ValueError(f"unknown language {language!r}; choose one of {', '.join(LANGUAGES)}") from None


def _scope(language: str) -> list[Language]:
    if language == "both":
        return list(LANGUAGES)
    if language not in LANGUAGES:
        raise ValueError(f"unknown language {language!r}; choose english, persian or both")
    return [language]  # type: ignore[list-item]


def _max_quatrain() -> int:
    return max(corpus("english").quatrains)


def _check_n(n: int) -> None:
    if n < 1 or n > _max_quatrain():
        raise ValueError(f"quatrain {n} does not exist; valid numbers are 1-{_max_quatrain()}")


def _texts(n: int, languages: list[Language]) -> dict[str, list[str]]:
    return {lang: [line.text for line in corpus(lang).quatrain(n)] for lang in languages}


def _attribution(lang: str, n: int) -> str:
    if lang == "persian":
        return f"{ATTRIBUTION[lang]}، رباعی {n}"
    return f"{ATTRIBUTION[lang]}, quatrain {n}"


def render(n: int, languages: list[Language], fmt: str) -> dict:
    """Return quatrain ``n`` as data, plus a ``formatted`` string for text formats."""
    texts = _texts(n, languages)
    out = {
        "quatrain": n,
        **texts,
        "attribution": {lang: _attribution(lang, n) for lang in languages},
    }
    if fmt != "json":
        out["format"] = fmt
        out["formatted"] = format_quatrain(n, languages, fmt)
    return out


def format_quatrain(n: int, languages: list[Language], fmt: str) -> str:
    """Render quatrain ``n`` as plain text, Markdown or HTML with attribution."""
    texts = _texts(n, languages)
    if fmt == "plain":
        blocks = ["\n".join(texts[lang]) + f"\n— {_attribution(lang, n)}" for lang in languages]
        return "\n\n".join(blocks)
    if fmt == "markdown":
        blocks = []
        for lang in languages:
            quote = "\n".join(f"> {line}  " for line in texts[lang])
            blocks.append(f"{quote}\n>\n> — *{_attribution(lang, n)}*")
        return "\n\n".join(blocks)
    if fmt == "html":
        blocks = []
        for lang in languages:
            rtl = ' lang="fa" dir="rtl"' if lang == "persian" else ' lang="en"'
            lines = "<br>\n    ".join(_escape(line) for line in texts[lang])
            blocks.append(
                f'<blockquote class="rubai"{rtl}>\n  <p>\n    {lines}\n  </p>\n'
                f"  <footer>— {_escape(_attribution(lang, n))}</footer>\n</blockquote>"
            )
        return "\n".join(blocks)
    raise ValueError(f"unknown format {fmt!r}; choose json, plain, markdown or html")


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# --------------------------------------------------------------------- tools


@server.tool()
def get_quatrain(n: int, language: Scope = "both", format: Format = "json") -> dict:
    """Return quatrain n (1-75) in English, Persian or both, ready to quote.

    The result always holds the lines per language and an attribution string.
    With format 'plain', 'markdown' (a blockquote) or 'html' (a <blockquote>
    with lang/dir attributes) it also holds a 'formatted' field: the quatrain
    with attribution appended, ready to paste into an artifact.
    """
    _check_n(n)
    return render(n, _scope(language), format)


@server.tool()
def find_quatrains(
    query: str | None = None,
    theme: str | None = None,
    language: Scope = "both",
    limit: int = 10,
) -> dict:
    """Find quatrains by keyword(s) and/or theme, ranked by how strongly they match.

    query: one or more words (English or Persian); a quatrain matches when a
    line contains any of them as a whole word. theme: a name from list_themes,
    which expands to curated words in both languages. language limits which
    text is searched; results always include both texts of each quatrain so
    the original and the translation can be shown together.
    """
    if not query and not theme:
        raise ValueError("give a query, a theme, or both")
    languages = _scope(language)
    combined: dict[int, dict] = {}
    for lang in languages:
        words: list[str] = []
        if query:
            words.extend(query.split())
        if theme:
            words.extend(theme_words(theme, lang))
        for n, hit in corpus(lang).match_quatrains(words).items():
            entry = combined.setdefault(n, {"quatrain": n, "score": 0, "matches": {}})
            entry["score"] += hit["score"]
            entry["matches"][lang] = {"words": hit["matched_words"], "lines": hit["matched_lines"]}
    ranked = sorted(combined.values(), key=lambda e: (-e["score"], e["quatrain"]))
    results = []
    for entry in ranked[: limit or None]:
        n = entry["quatrain"]
        results.append({**entry, **_texts(n, list(LANGUAGES))})
    return {
        "query": query,
        "theme": theme,
        "searched": languages,
        "total_matches": len(ranked),
        "returned": len(results),
        "results": results,
    }


@server.tool()
def random_quatrain(language: Scope = "both", theme: str | None = None, format: Format = "json") -> dict:
    """Pick a random quatrain, optionally restricted to a theme, in the requested format."""
    languages = _scope(language)
    if theme:
        candidates: set[int] = set()
        for lang in languages:
            candidates.update(corpus(lang).match_quatrains(theme_words(theme, lang)))
        if not candidates:
            raise ValueError(f"no quatrain matches theme {theme!r}")
        n = random.choice(sorted(candidates))
    else:
        n = random.randint(1, _max_quatrain())
    return render(n, languages, format)


@server.tool()
def browse_quatrains(language: Language = "english", start: int = 1, count: int = 75) -> dict:
    """List quatrains by number with their first line, for skimming the poem or picking one to fetch."""
    c = corpus(language)
    _check_n(start)
    numbers = sorted(c.quatrains)
    chosen = [n for n in numbers if n >= start][: max(count, 0) or None]
    return {
        "language": language,
        "total": len(numbers),
        "quatrains": [{"quatrain": n, "first_line": c.quatrain(n)[0].text} for n in chosen],
    }


@server.tool()
def list_themes() -> dict:
    """List the themes find_quatrains and random_quatrain accept, with their keywords and quatrain counts."""
    out = []
    for name, spec in THEMES.items():
        matched: set[int] = set()
        for lang in LANGUAGES:
            matched.update(corpus(lang).match_quatrains(spec[lang]))  # type: ignore[arg-type]
        out.append(
            {
                "theme": name,
                "description": spec["description"],
                "english_words": spec["english"],
                "persian_words": spec["persian"],
                "quatrains": len(matched),
            }
        )
    return {"themes": out}


@server.tool()
def corpus_info() -> dict:
    """Describe the texts: source files, number of quatrains and lines, vocabulary size, and attribution."""
    return {
        "corpora": [{**c.summary(), "attribution": ATTRIBUTION[c.language]} for c in corpora().values()],
        "note": "Quatrain numbers are aligned between the English and Persian texts.",
    }


@server.tool()
def word_frequency(
    language: Language = "english",
    top_n: int = 50,
    exclude_stopwords: bool = True,
) -> dict:
    """Rank the most frequent words in one text (function words excluded by default).

    A quick way to see which images dominate the poem before choosing a theme
    or keyword for find_quatrains.
    """
    c = corpus(language)
    rows = c.frequency(top_n=top_n or None, exclude_stopwords=exclude_stopwords)
    return {"language": language, "total_tokens": c.total_tokens, "returned": len(rows), "words": rows}


# ----------------------------------------------------------------- resources


@server.resource("rubaiyat://{language}/quatrain/{n}", mime_type="text/plain")
def quatrain_resource(language: str, n: int) -> str:
    """One quatrain as plain text with attribution, e.g. rubaiyat://english/quatrain/12."""
    _check_n(n)
    return format_quatrain(n, _scope(language), "plain")


@server.resource("rubaiyat://{language}/text", mime_type="text/plain")
def full_text_resource(language: str) -> str:
    """The whole poem in one language, quatrains numbered and separated by blank lines."""
    c = corpus(language)
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
