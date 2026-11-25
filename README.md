# Rubaiyat of Khayyam in XML

Rubaiyat of Khayyam encoded in plain XML and TEI standard.

## Language

This repository includes Rubaiyat in Persian and English. The English translation was done by Edward FitzGerald.

## Disclaimer

I assure you that the XML files are well-formed but I don't guarantee the complete correctness of the TEI version of these files.

## MCP server: find and quote quatrains

The `rubaiyat_mcp` package exposes the two aligned texts (`english.xml`,
`persian.xml`; 75 quatrains of 4 lines each) to any MCP client, so an
assistant can look up a quatrain by number, find quatrains by keyword or
theme, pick one at random, and get the text back with attribution, ready to
drop into a document, slide, web page or other artifact. Quatrain *n* in one
language is the counterpart of quatrain *n* in the other, so the original
and the translation can always be shown together.

### Tools

| Tool | What it does |
| --- | --- |
| `get_quatrain` | Quatrain *n* in English, Persian or both. `format` of `plain`, `markdown` or `html` adds a quote-ready `formatted` string with attribution (the HTML carries `lang`/`dir="rtl"` for Persian) |
| `find_quatrains` | Keyword and/or theme search, ranked by match strength; each result carries both texts and which words and lines matched |
| `random_quatrain` | A random quatrain, optionally within a theme, in any format |
| `browse_quatrains` | Numbered list of first lines for skimming the poem |
| `list_themes` | The available themes (wine, mortality, time, fate, love, nature, joy, faith, potter, kings, mystery, cosmos, sorrow) with their keywords in both languages |
| `corpus_info` | Source files, counts and attribution strings |
| `word_frequency` | Most frequent words in one text, to see which images dominate before choosing a keyword |

Resources: `rubaiyat://{language}/quatrain/{n}` (plain text with attribution)
and `rubaiyat://{language}/text` (the whole poem).

Matching ignores case, and Persian queries match whether typed with the
Arabic yeh/kaf (`ي`, `ك`, as in the XML) or the Persian forms (`ی`, `ک`).
Theme search is keyword-based, not semantic; every theme word occurs in the
text, so each theme returns results in both languages.

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
