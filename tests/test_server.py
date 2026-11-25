"""Tests for the retrieval tools, directly and end-to-end over stdio."""

import json
import sys

import anyio
import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from rubaiyat_mcp import server as srv
from rubaiyat_mcp.themes import THEMES


def test_get_quatrain_json_has_both_texts_and_attribution():
    out = srv.get_quatrain(1)
    assert out["quatrain"] == 1
    assert out["english"][0].startswith("WAKE!") and len(out["persian"]) == 4
    assert "FitzGerald" in out["attribution"]["english"] and "خیام" in out["attribution"]["persian"]


def test_get_quatrain_formats():
    out = srv.get_quatrain(12, language="english", format="markdown")
    assert out["format"] == "markdown" and out["english"] and "persian" not in out
    assert out["formatted"].startswith("> ") and "— *Omar Khayyam" in out["formatted"]
    html = srv.get_quatrain(12, format="html")["formatted"]
    assert '<blockquote class="rubai" lang="fa" dir="rtl">' in html and "<footer>" in html
    plain = srv.get_quatrain(12, language="persian", format="plain")["formatted"]
    assert plain.count("\n") == 4 and "رباعی 12" in plain
    assert "formatted" not in srv.get_quatrain(12)


def test_get_quatrain_rejects_bad_number_and_format():
    with pytest.raises(ValueError):
        srv.get_quatrain(76)
    with pytest.raises(ValueError):
        srv.get_quatrain(1, format="yaml")


def test_find_quatrains_by_keyword_ranks_and_returns_both_texts():
    out = srv.find_quatrains(query="wine", language="english")
    assert out["total_matches"] == 8
    top = out["results"][0]
    assert top["quatrain"] == 6  # "Wine! Wine! Wine! / Red Wine!"
    assert top["score"] == 4 and top["matches"]["english"]["words"] == ["wine"]
    assert len(top["english"]) == 4 and len(top["persian"]) == 4


def test_find_quatrains_persian_spelling_variants_match():
    arabic_yeh = srv.find_quatrains(query="مي", language="persian")
    persian_yeh = srv.find_quatrains(query="می", language="persian")
    assert arabic_yeh["total_matches"] == persian_yeh["total_matches"] > 0


def test_find_quatrains_by_theme_and_limit():
    out = srv.find_quatrains(theme="potter", limit=3)
    assert out["returned"] == 3 and out["total_matches"] >= 3
    assert all(e["score"] >= out["results"][-1]["score"] for e in out["results"])
    with pytest.raises(KeyError):
        srv.find_quatrains(theme="spaceships")
    with pytest.raises(ValueError):
        srv.find_quatrains()


def test_every_theme_returns_results_in_both_languages():
    for name in THEMES:
        for lang in ("english", "persian"):
            assert srv.find_quatrains(theme=name, language=lang)["total_matches"] > 0, (name, lang)


def test_random_quatrain_respects_theme():
    hits = {e["quatrain"] for e in srv.find_quatrains(theme="kings", limit=0)["results"]}
    for _ in range(10):
        out = srv.random_quatrain(theme="kings")
        assert out["quatrain"] in hits


def test_browse_and_list_themes():
    page = srv.browse_quatrains("persian", start=70, count=10)
    assert [q["quatrain"] for q in page["quatrains"]] == [70, 71, 72, 73, 74, 75]
    themes = srv.list_themes()["themes"]
    assert {t["theme"] for t in themes} == set(THEMES) and all(t["quatrains"] > 0 for t in themes)


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
                    "get_quatrain", "find_quatrains", "random_quatrain", "browse_quatrains",
                    "list_themes", "corpus_info", "word_frequency",
                } <= tools

                q = _payload(await session.call_tool("get_quatrain", {"n": 1}))
                assert q["english"][0].startswith("WAKE!")

                md = _payload(await session.call_tool(
                    "get_quatrain", {"n": 7, "language": "english", "format": "markdown"}))
                assert md["formatted"].startswith("> Come, fill the Cup")

                found = _payload(await session.call_tool("find_quatrains", {"theme": "wine", "limit": 2}))
                assert found["returned"] == 2 and "persian" in found["results"][0]

                assert _is_error(await session.call_tool("get_quatrain", {"n": 99}))

                res = await session.read_resource("rubaiyat://persian/quatrain/2")
                assert "ميخانه" in res.contents[0].text and "رباعی 2" in res.contents[0].text

    anyio.run(main)
