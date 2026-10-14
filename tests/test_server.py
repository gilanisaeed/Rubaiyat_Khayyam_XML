"""End-to-end test: spawn the server over stdio and call tools through an MCP client."""

import json
import sys

import anyio
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def _session():
    params = StdioServerParameters(command=sys.executable, args=["-m", "rubaiyat_mcp"])
    return stdio_client(params)


def _run(coro_fn):
    return anyio.run(coro_fn)


def _payload(result):
    # mcp 2.x uses snake_case field names; 1.x used camelCase.
    structured = getattr(result, "structured_content", None) or getattr(result, "structuredContent", None)
    if structured:
        return structured
    return json.loads(result.content[0].text)


def _is_error(result):
    return bool(getattr(result, "is_error", None) or getattr(result, "isError", None))


def test_tools_and_resources_over_stdio():
    async def main():
        async with await _session() as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = {t.name for t in (await session.list_tools()).tools}
                assert {
                    "corpus_info", "word_frequency", "ngram_frequency", "word_context",
                    "word_distribution", "search_lines", "get_quatrain", "compare_word_frequency",
                } <= tools

                info = _payload(await session.call_tool("corpus_info", {}))
                assert {c["language"] for c in info["corpora"]} == {"english", "persian"}

                freq = _payload(await session.call_tool(
                    "word_frequency", {"language": "persian", "top_n": 3, "exclude_stopwords": True}))
                assert freq["returned"] == 3 and freq["words"][0]["count"] >= freq["words"][2]["count"]

                ctx = _payload(await session.call_tool(
                    "word_context", {"word": "wine", "language": "english", "max_results": 2}))
                assert ctx["total_count"] > ctx["returned"] == 2
                assert ctx["occurrences"][0]["translation"]["language"] == "persian"

                q = _payload(await session.call_tool("get_quatrain", {"n": 1}))
                assert q["english"][0].startswith("WAKE!") and len(q["persian"]) == 4

                err = await session.call_tool("get_quatrain", {"n": 99})
                assert _is_error(err)

                res = await session.read_resource("rubaiyat://persian/quatrain/2")
                assert "ميخانه" in res.contents[0].text

    _run(main)
