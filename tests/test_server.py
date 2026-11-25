"""Tests for the retrieval tools, directly and end-to-end over stdio."""

import json
import sys

import anyio
import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from rubaiyat_mcp import server as srv
from rubaiyat_mcp.glosses import Glossary
from rubaiyat_mcp.themes import THEMES


def test_glossary_covers_every_quatrain_and_related_is_symmetric():
    g = Glossary.load()
    for lang in ("english", "persian"):
        for n in range(1, 76):
            entry = g.get(lang, n)
            assert entry.gloss and entry.tags
    assert g.get("english", 12).related == (11,)  # "A Book of Verses" <-> "تنگي مي لعل خواهم و ديواني"
    assert 12 in g.get("persian", 11).related and 11 in g.get("persian", 11).related
    assert g.get("english", 69).related == (49,)  # chess pieces <-> puppets
    assert g.get("english", 34).related == ()


def test_get_quatrain_uses_curated_related_not_number():
    out = srv.get_quatrain(12)
    assert out["language"] == "english" and out["lines"][0].startswith("A Book of Verses")
    assert [r["quatrain"] for r in out["related"]] == [11]
    assert out["related"][0]["language"] == "persian" and "ديواني" in out["related"][0]["lines"][0]
    assert "gloss" in out and "FitzGerald" in out["attribution"]
    none = srv.get_quatrain(34)
    assert none["related"] == [] and "no corresponding" in none["related_note"]


def test_get_quatrain_formats_include_related_blocks():
    md = srv.get_quatrain(12, format="markdown")
    assert md["formatted"].startswith("> A Book of Verses") and md["formatted"].count("— *") == 2
    html = srv.get_quatrain(12, format="html", include_related=False)
    assert html["formatted"].count("<blockquote") == 1 and 'lang="en"' in html["formatted"]
    fa = srv.get_quatrain(11, language="persian", format="html", include_related=False)["formatted"]
    assert 'lang="fa" dir="rtl"' in fa and "رباعی 11" in fa
    plain = srv.get_quatrain(1, language="persian", format="plain", include_related=False)["formatted"]
    assert plain.count("\n") == 4
    assert "formatted" not in srv.get_quatrain(1)


def test_get_quatrain_rejects_bad_number_and_format():
    with pytest.raises(ValueError):
        srv.get_quatrain(76)
    with pytest.raises(ValueError):
        srv.get_quatrain(1, format="yaml")


def test_find_quatrains_text_match_ranks_first():
    out = srv.find_quatrains(query="wine", language="english")
    top = out["results"][0]
    assert top["quatrain"] == 6 and top["matched"]["text"] == ["wine"]
    assert all(r["language"] == "english" for r in out["results"])
    assert "persian" in {rel["language"] for r in out["results"] for rel in r["related"]}


def test_find_quatrains_english_query_reaches_persian_via_gloss():
    out = srv.find_quatrains(query="potter", language="persian", limit=0)
    numbers = {r["quatrain"] for r in out["results"]}
    assert {36, 59, 60}.issubset(numbers)
    assert all(r["matched"]["gloss_or_tags"] for r in out["results"])


def test_find_quatrains_paraphrase_words_hit_gloss():
    out = srv.find_quatrains(query="fear death", language="english", limit=5)
    assert out["total_matches"] >= 5
    assert any(r["quatrain"] == 46 for r in out["results"])  # "fear not lest Existence..."


def test_find_quatrains_ignores_function_words_in_multiword_query():
    out = srv.find_quatrains(query="accepting death without fear", language="english", limit=3)
    assert out["results"][0]["quatrain"] == 46
    assert "without" not in out["results"][0]["matched"]["text"]
    # a query made only of stopwords still searches literally
    assert srv.find_quatrains(query="the", language="english")["total_matches"] > 0


def test_find_quatrains_ranks_coverage_over_repetition():
    out = srv.find_quatrains(query="simple life bread wine", language="english", limit=3)
    assert out["results"][0]["quatrain"] == 12  # "A Jug of Wine, a Loaf of Bread" beats "Wine! Wine! Wine!"


def test_find_quatrains_persian_spelling_variants_match():
    a = srv.find_quatrains(query="مي", language="persian")
    b = srv.find_quatrains(query="می", language="persian")
    assert a["total_matches"] == b["total_matches"] > 0


def test_find_quatrains_theme_limit_and_errors():
    out = srv.find_quatrains(theme="potter", limit=3)
    assert out["returned"] == 3 and out["total_matches"] > 3
    scores = [r["score"] for r in out["results"]]
    assert scores == sorted(scores, reverse=True)
    with pytest.raises(KeyError):
        srv.find_quatrains(theme="spaceships")
    with pytest.raises(ValueError):
        srv.find_quatrains()


def test_every_theme_returns_results_in_both_languages():
    for name in THEMES:
        for lang in ("english", "persian"):
            assert srv.find_quatrains(theme=name, language=lang)["total_matches"] > 0, (name, lang)


def test_all_quatrains_and_browse():
    out = srv.all_quatrains("persian")
    assert out["count"] == 75 and len(out["quatrains"][10]["lines"]) == 4
    assert out["quatrains"][10]["related"] == [11, 12]  # Persian 11 feeds English 11 and 12
    brief = srv.all_quatrains("english", include_text=False)
    assert "lines" not in brief["quatrains"][0] and brief["quatrains"][0]["gloss"]
    page = srv.browse_quatrains("english", start=70, count=10)
    assert [q["quatrain"] for q in page["quatrains"]] == [70, 71, 72, 73, 74, 75]
    assert page["quatrains"][0]["gloss"]


def test_random_quatrain_respects_theme_and_language():
    hits = {r["quatrain"] for r in srv.find_quatrains(theme="kings", language="persian", limit=0)["results"]}
    for _ in range(10):
        out = srv.random_quatrain(language="persian", theme="kings")
        assert out["language"] == "persian" and out["quatrain"] in hits


def test_list_themes_and_corpus_info():
    themes = srv.list_themes()["themes"]
    assert {t["theme"] for t in themes} == set(THEMES)
    assert all(t["quatrains"]["english"] > 0 and t["quatrains"]["persian"] > 0 for t in themes)
    info = srv.corpus_info()
    assert "do not correspond" in info["relationship"]


# ------------------------------------------------------------ end to end


def _payload(result):
    structured = getattr(result, "structured_content", None) or getattr(result, "structuredContent", None)
    if structured:
        return structured
    return json.loads(result.content[0].text)


def _is_error(result):
    return bool(getattr(result, "is_error", None) or getattr(result, "isError", None))


def test_tools_and_resources_over_stdio():
    async def main():
        params = StdioServerParameters(command=sys.executable, args=["-m", "rubaiyat_mcp"])
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = {t.name for t in (await session.list_tools()).tools}
                assert {
                    "get_quatrain", "find_quatrains", "all_quatrains", "random_quatrain",
                    "browse_quatrains", "list_themes", "corpus_info", "word_frequency",
                } <= tools

                q = _payload(await session.call_tool("get_quatrain", {"n": 1}))
                assert q["lines"][0].startswith("WAKE!") and q["related"][0]["language"] == "persian"

                md = _payload(await session.call_tool(
                    "get_quatrain", {"n": 7, "format": "markdown", "include_related": False}))
                assert md["formatted"].startswith("> Come, fill the Cup")

                found = _payload(await session.call_tool("find_quatrains", {"theme": "wine", "limit": 2}))
                assert found["returned"] == 2 and "gloss" in found["results"][0]

                everything = _payload(await session.call_tool("all_quatrains", {"language": "english"}))
                assert everything["count"] == 75

                assert _is_error(await session.call_tool("get_quatrain", {"n": 99}))

                res = await session.read_resource("rubaiyat://persian/quatrain/2")
                assert "ميخانه" in res.contents[0].text and "رباعی 2" in res.contents[0].text

    anyio.run(main)
