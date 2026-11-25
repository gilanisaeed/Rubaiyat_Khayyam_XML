"""MCP server for finding and quoting quatrains from the Rubaiyat of Khayyam.

The server exposes the two texts in this repository, Edward FitzGerald's
English translation and a Persian collection of Khayyam's quatrains, so an
assistant can look up a quatrain by number, find quatrains by keyword, theme
or paraphrase, pick one at random, read the whole poem, and get the text
back formatted with attribution for use in documents, slides and web pages.

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
from rubaiyat_mcp.corpus import LANGUAGES, STOPWORDS, Corpus, Language, load_corpora, normalize
from rubaiyat_mcp.glosses import Glossary
from rubaiyat_mcp.themes import THEMES, theme_words

Scope = Literal["english", "persian", "both"]
Format = Literal["json", "plain", "markdown", "html"]

ATTRIBUTION = {
    "english": "Omar Khayyam, translated by Edward FitzGerald",
    "persian": "عمر خیام",
}
OTHER: dict[str, Language] = {"english": "persian", "persian": "english"}

INSTRUCTIONS = """\
Look up and quote quatrains (rubaiyat) of Omar Khayyam. Two texts are
available, each of 75 four-line quatrains: 'english' (Edward FitzGerald's
translation) and 'persian' (the original). They are separate collections, not
line-by-line translations, and quatrain numbers do NOT correspond between
them. Where an English quatrain draws on a Persian one, get_quatrain and
find_quatrains report it under 'related'; never pair the texts by number.

How to find a quatrain:
- A specific number: get_quatrain(n, language).
- A word or image the quatrain uses: find_quatrains(query=...). It also
  searches a one-sentence English summary and tags of every quatrain, so
  English queries find Persian quatrains too.
- A broad subject: find_quatrains(theme=...) with a name from list_themes.
- A paraphrase, mood or idea ("something about accepting death without
  fear"): call all_quatrains(language) once, read the 75 summaries and
  texts, and choose yourself. The whole text is short.
- A quick epigraph: random_quatrain.

Use format='markdown' or 'html' on get_quatrain / random_quatrain to receive
quote-ready text with attribution for an artifact. Matching ignores case and
Persian spelling variants.
"""

server = MCPServer(
    name="rubaiyat",
    title="Rubaiyat of Khayyam",
    instructions=INSTRUCTIONS,
    version=__version__,
)

_corpora: dict[Language, Corpus] | None = None
_glossary: Glossary | None = None


def corpora() -> dict[Language, Corpus]:
    """Parse the XML files on first use and cache them for the process."""
    global _corpora
    if _corpora is None:
        _corpora = load_corpora()
    return _corpora


def glossary() -> Glossary:
    global _glossary
    if _glossary is None:
        _glossary = Glossary.load()
    return _glossary


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


def _max_quatrain(language: str) -> int:
    return max(corpus(language).quatrains)


def _check_n(language: str, n: int) -> None:
    if n < 1 or n > _max_quatrain(language):
        raise ValueError(f"quatrain {n} does not exist; valid numbers are 1-{_max_quatrain(language)}")


def _lines(language: str, n: int) -> list[str]:
    return [line.text for line in corpus(language).quatrain(n)]


def _attribution(lang: str, n: int) -> str:
    if lang == "persian":
        return f"{ATTRIBUTION[lang]}، رباعی {n}"
    return f"{ATTRIBUTION[lang]}, quatrain {n}"


def _entry(language: str, n: int, *, related: bool = True) -> dict:
    """The standard description of one quatrain: text, summary, tags, attribution."""
    g = glossary().get(language, n)
    out = {
        "language": language,
        "quatrain": n,
        "lines": _lines(language, n),
        "gloss": g.gloss,
        "tags": list(g.tags),
        "attribution": _attribution(language, n),
    }
    if related:
        other = OTHER[language]
        out["related"] = [_entry(other, m, related=False) for m in g.related]
        out["related_note"] = (
            f"{other} quatrains this one corresponds to (same source, not a literal translation)"
            if g.related
            else f"no corresponding {other} quatrain in this collection"
        )
    return out


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def format_block(language: str, n: int, fmt: str) -> str:
    """Render one quatrain as plain text, Markdown or HTML with attribution."""
    lines = _lines(language, n)
    attribution = _attribution(language, n)
    if fmt == "plain":
        return "\n".join(lines) + f"\n— {attribution}"
    if fmt == "markdown":
        quote = "\n".join(f"> {line}  " for line in lines)
        return f"{quote}\n>\n> — *{attribution}*"
    if fmt == "html":
        attrs = ' lang="fa" dir="rtl"' if language == "persian" else ' lang="en"'
        body = "<br>\n    ".join(_escape(line) for line in lines)
        return (
            f'<blockquote class="rubai"{attrs}>\n  <p>\n    {body}\n  </p>\n'
            f"  <footer>— {_escape(attribution)}</footer>\n</blockquote>"
        )
    raise ValueError(f"unknown format {fmt!r}; choose json, plain, markdown or html")


def render(language: str, n: int, fmt: str, include_related: bool) -> dict:
    """``_entry`` plus, for text formats, a ``formatted`` string ready to paste."""
    out = _entry(language, n, related=include_related)
    if fmt != "json":
        blocks = [format_block(language, n, fmt)]
        if include_related:
            for rel in out["related"]:
                blocks.append(format_block(rel["language"], rel["quatrain"], fmt))
        out["format"] = fmt
        out["formatted"] = "\n\n".join(blocks)
    return out


def _content_words(words: list[str]) -> list[str]:
    """Drop function words from a multi-word query so 'without' or 'که' cannot dominate the ranking."""
    kept = [w for w in words if normalize(w, "english") not in STOPWORDS["english"]
            and normalize(w, "persian") not in STOPWORDS["persian"]]
    return kept or words


def _search(language: Language, words: list[str], gloss_words: list[str]) -> dict[int, dict]:
    """Score quatrains of one collection against text words and English gloss/tag words.

    Covering more distinct query words outranks repeating one word, so a
    quatrain matching three of four words beats one that says 'wine' thrice.
    Within equal coverage, text hits count double gloss/tag hits.
    """
    hits: dict[int, dict] = {}
    for n, h in corpus(language).match_quatrains(words).items():
        e = hits.setdefault(n, {"raw": 0, "text_words": [], "gloss_words": []})
        e["raw"] += 2 * h["score"]
        e["text_words"] = h["matched_words"]
    for n, h in glossary().match(language, gloss_words).items():
        e = hits.setdefault(n, {"raw": 0, "text_words": [], "gloss_words": []})
        e["raw"] += h["score"]
        e["gloss_words"] = h["matched_words"]
    for e in hits.values():
        distinct = len({normalize(w, "english") for w in e["text_words"] + e["gloss_words"]})
        e["score"] = 10 * distinct + e.pop("raw")
    return hits


# --------------------------------------------------------------------- tools


@server.tool()
def get_quatrain(
    n: int,
    language: Language = "english",
    format: Format = "json",
    include_related: bool = True,
) -> dict:
    """Return quatrain n (1-75) of one text, with its summary, tags and attribution, ready to quote.

    With include_related the corresponding quatrains in the other language
    are attached (curated correspondences, not number matching). format
    'plain', 'markdown' (blockquote) or 'html' (<blockquote> with lang/dir)
    adds a 'formatted' string with attribution, including the related
    quatrains, ready to paste into an artifact.
    """
    _check_n(language, n)
    return render(language, n, format, include_related)


@server.tool()
def find_quatrains(
    query: str | None = None,
    theme: str | None = None,
    language: Scope = "both",
    limit: int = 10,
) -> dict:
    """Find quatrains by keyword(s) and/or theme, ranked by match strength.

    query: one or more words, English or Persian. Each is matched as a whole
    word in the text and, in English, in every quatrain's one-sentence
    summary and tags, so an English query reaches Persian quatrains too.
    theme: a name from list_themes, expanded to curated words. language
    chooses which collection(s) to search. Each result carries the text,
    summary, tags, attribution and related quatrains in the other language.
    For a paraphrase or mood rather than a word, use all_quatrains instead.
    """
    if not query and not theme:
        raise ValueError("give a query, a theme, or both")
    query_words = _content_words(query.split()) if query else []
    results = []
    for lang in _scope(language):
        words = list(query_words)
        gloss_words = list(query_words)
        if theme:
            words += theme_words(theme, lang)
            gloss_words += theme_words(theme, "english")
        for n, h in _search(lang, words, gloss_words).items():
            results.append(
                {
                    "score": h["score"],
                    "matched": {"text": h["text_words"], "gloss_or_tags": h["gloss_words"]},
                    **_entry(lang, n),
                }
            )
    results.sort(key=lambda e: (-e["score"], e["language"], e["quatrain"]))
    return {
        "query": query,
        "theme": theme,
        "searched": _scope(language),
        "total_matches": len(results),
        "returned": min(len(results), limit) if limit else len(results),
        "results": results[: limit or None],
    }


@server.tool()
def all_quatrains(language: Language = "english", include_text: bool = True) -> dict:
    """Return every quatrain of one text with its summary and tags, for reading and choosing directly.

    The whole collection is small (75 quatrains, about 2500 words), so for a
    paraphrased request read it and pick, rather than guessing keywords.
    Set include_text=false for summaries only.
    """
    c = corpus(language)
    items = []
    for n in sorted(c.quatrains):
        g = glossary().get(language, n)
        item = {"quatrain": n, "gloss": g.gloss, "tags": list(g.tags), "related": list(g.related)}
        if include_text:
            item["lines"] = _lines(language, n)
        items.append(item)
    return {
        "language": language,
        "attribution": ATTRIBUTION[language],
        "count": len(items),
        "related_means": f"numbers of corresponding {OTHER[language]} quatrains",
        "quatrains": items,
    }


@server.tool()
def random_quatrain(
    language: Language = "english",
    theme: str | None = None,
    format: Format = "json",
    include_related: bool = True,
) -> dict:
    """Pick a random quatrain from one text, optionally within a theme, in the requested format."""
    if theme:
        candidates = set(_search(language, theme_words(theme, language), theme_words(theme, "english")))
        if not candidates:
            raise ValueError(f"no {language} quatrain matches theme {theme!r}")
        n = random.choice(sorted(candidates))
    else:
        n = random.randint(1, _max_quatrain(language))
    return render(language, n, format, include_related)


@server.tool()
def browse_quatrains(language: Language = "english", start: int = 1, count: int = 75) -> dict:
    """List quatrains of one text by number with first line and summary, for skimming."""
    c = corpus(language)
    _check_n(language, start)
    numbers = [n for n in sorted(c.quatrains) if n >= start][: max(count, 0) or None]
    return {
        "language": language,
        "total": len(c.quatrains),
        "quatrains": [
            {"quatrain": n, "first_line": c.quatrain(n)[0].text, "gloss": glossary().get(language, n).gloss}
            for n in numbers
        ],
    }


@server.tool()
def list_themes() -> dict:
    """List the themes find_quatrains and random_quatrain accept, with keywords and match counts per text."""
    out = []
    for name, spec in THEMES.items():
        counts = {
            lang: len(_search(lang, list(spec[lang]), list(spec["english"])))  # type: ignore[arg-type]
            for lang in LANGUAGES
        }
        out.append(
            {
                "theme": name,
                "description": spec["description"],
                "english_words": spec["english"],
                "persian_words": spec["persian"],
                "quatrains": counts,
            }
        )
    return {"themes": out}


@server.tool()
def corpus_info() -> dict:
    """Describe the texts: source files, counts, attribution, and how the two collections relate."""
    paired = sum(1 for n in range(1, 76) if glossary().get("english", n).related)
    return {
        "corpora": [{**c.summary(), "attribution": ATTRIBUTION[c.language]} for c in corpora().values()],
        "relationship": (
            "The English and Persian texts are separate collections; quatrain numbers do not correspond. "
            f"{paired} of the 75 English quatrains have a curated 'related' Persian counterpart."
        ),
    }


@server.tool()
def word_frequency(
    language: Language = "english",
    top_n: int = 50,
    exclude_stopwords: bool = True,
) -> dict:
    """Rank the most frequent words in one text (function words excluded by default).

    A quick way to see which images dominate the poem before choosing a
    keyword for find_quatrains.
    """
    c = corpus(language)
    rows = c.frequency(top_n=top_n or None, exclude_stopwords=exclude_stopwords)
    return {"language": language, "total_tokens": c.total_tokens, "returned": len(rows), "words": rows}


# ----------------------------------------------------------------- resources


@server.resource("rubaiyat://{language}/quatrain/{n}", mime_type="text/plain")
def quatrain_resource(language: str, n: int) -> str:
    """One quatrain as plain text with attribution, e.g. rubaiyat://english/quatrain/12."""
    _check_n(language, n)
    return format_block(language, n, "plain")


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
    glossary()
    server.run(transport=args.transport)


if __name__ == "__main__":
    main()
