# Rubaiyat of Khayyam in XML

Rubaiyat of Khayyam encoded in plain XML and TEI standard.

## Language

This repository includes Rubaiyat in Persian and English. The English translation was done by Edward FitzGerald.

## Disclaimer

I assure you that the XML files are well-formed but I don't guarantee the complete correctness of the TEI version of these files.

## MCP server: word frequency and concordance

The `rubaiyat_mcp` package exposes the two aligned corpora (`english.xml`,
`persian.xml`; 75 quatrains of 4 lines each) to any MCP client as a set of
word-frequency and concordance tools. Words are matched after normalisation:
English is lower-cased, and Persian has the Arabic yeh/kaf (`ي`, `ك`) folded
to the Persian forms (`ی`, `ک`) with short-vowel diacritics removed, so
either spelling finds the same word.

### Tools

| Tool | What it returns |
| --- | --- |
| `corpus_info` | Quatrain, line, token, vocabulary and hapax counts per language |
| `word_frequency` | Ranked word list with count, rate per 1000 tokens and quatrains containing the word; filters for stopwords, length, prefix and substring |
| `ngram_frequency` | Most frequent bigrams/trigrams (2 to 6) within lines |
| `word_context` | Every line containing a word, with its full quatrain and the aligned quatrain in the other language (a concordance) |
| `word_distribution` | A word's count quatrain by quatrain |
| `search_lines` | Substring or regex search over lines in one or both languages |
| `get_quatrain` | Quatrain *n* in English, Persian, or both |
| `compare_word_frequency` | An English word against a Persian word: counts and shared / distinct quatrains |

Resources: `rubaiyat://{language}/quatrain/{n}` and `rubaiyat://{language}/text`.

### Running it

Requires Python 3.10+ and the `mcp` package (1.2 or newer; 2.x is supported).

```sh
uv run rubaiyat-mcp                        # stdio transport (default)
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
