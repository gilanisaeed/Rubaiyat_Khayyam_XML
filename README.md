# Rubaiyat of Khayyam in XML

Rubaiyat of Khayyam encoded in plain XML and TEI standard.

## Language

This repository includes Rubaiyat in Persian and English. The English translation was done by Edward FitzGerald.

## Disclaimer

I assure you that the XML files are well-formed but I don't guarantee the complete correctness of the TEI version of these files.

## MCP server: find and quote quatrains

The `rubaiyat_mcp` package exposes the two texts (`english.xml`,
`persian.xml`; 75 quatrains of 4 lines each) to any MCP client, so an
assistant can look up a quatrain by number, find quatrains by keyword, theme
or paraphrase, pick one at random, and get the text back with attribution,
ready to drop into a document, slide, web page or other artifact.

**The two texts are separate collections, not line-by-line translations, and
quatrain numbers do not correspond between them.** FitzGerald's quatrain 12
("A Book of Verses underneath the Bough") draws on Persian quatrain 11, his
chess-pieces quatrain 69 on Persian 49, and about a third of the English
quatrains have no counterpart in the Persian file. `rubaiyat_mcp/glosses.json`
records these correspondences by hand (54 English quatrains have one), and the server reports them
under `related` instead of pairing by number.

The same file holds a one-sentence English summary and tags for every
quatrain in both languages. `find_quatrains` searches those as well as the
text, so an English query such as "potter" or "fear death" reaches Persian
quatrains and quatrains that use none of the query's words. For a mood or
paraphrase, `all_quatrains` returns the whole collection with summaries
(about 2,500 words) so the calling model can read it and choose.

### Tools

| Tool | What it does |
| --- | --- |
| `get_quatrain` | Quatrain *n* of one text with summary, tags, attribution and its `related` quatrains in the other language. `format` of `plain`, `markdown` or `html` adds a quote-ready `formatted` string (the HTML carries `lang`/`dir="rtl"` for Persian) |
| `find_quatrains` | Keyword and/or theme search over text, summaries and tags, ranked by match strength, in one or both collections |
| `all_quatrains` | Every quatrain of one text with summary and tags, for reading and choosing directly |
| `random_quatrain` | A random quatrain, optionally within a theme, in any format |
| `browse_quatrains` | Numbered list of first lines and summaries for skimming |
| `list_themes` | The 13 themes (wine, mortality, time, fate, love, nature, joy, faith, potter, kings, mystery, cosmos, sorrow) with keywords and match counts |
| `corpus_info` | Source files, counts, attribution and how the collections relate |
| `word_frequency` | Most frequent words in one text, to see which images dominate before choosing a keyword |

Resources: `rubaiyat://{language}/quatrain/{n}` (plain text with attribution)
and `rubaiyat://{language}/text` (the whole poem).

Matching ignores case, and Persian queries match whether typed with the
Arabic yeh/kaf (`ي`, `ك`, as in the XML) or the Persian forms (`ی`, `ک`).
Theme and keyword search is lexical, not semantic; the summaries are what
make paraphrased queries work.

### Running it

Requires Python 3.10+ and the `mcp` package (1.2 or newer; 2.x is supported).

```sh
uv run rubaiyat-mcp                               # stdio transport (default)
uv run rubaiyat-mcp --transport streamable-http   # HTTP on 127.0.0.1:8000/mcp
```

Or without `uv`: `pip install -e .` then `python -m rubaiyat_mcp`.

The repository's `.mcp.json` registers the server for Claude Code, so opening
this directory makes the `rubaiyat` tools available. For Claude Desktop or
another client, add the equivalent entry:

```json
{
  "mcpServers": {
    "rubaiyat": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/Rubaiyat_Khayyam_XML", "rubaiyat-mcp"]
    }
  }
}
```

Set `RUBAIYAT_XML_DIR` to point the server at XML files kept elsewhere.

### Tests

```sh
pip install -e ".[dev]"
python -m pytest
```
