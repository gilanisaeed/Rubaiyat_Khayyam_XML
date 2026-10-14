"""Load the Rubaiyat XML files and compute word statistics.

The repository ships two aligned corpora (``english.xml`` and ``persian.xml``),
each holding 75 quatrains (``<lg n="...">``) of four lines (``<l>``).
This module parses them once and exposes tokenisation, frequency and
concordance helpers that the MCP server wraps as tools.
"""

from __future__ import annotations

import os
import re
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator, Literal

Language = Literal["english", "persian"]
LANGUAGES: tuple[Language, ...] = ("english", "persian")

FILES: dict[Language, str] = {
    "english": "english.xml",
    "persian": "persian.xml",
}

# Words that carry little lexical meaning; used when ``exclude_stopwords`` is set.
STOPWORDS: dict[Language, frozenset[str]] = {
    "english": frozenset(
        """
        a about ah all am an and are as at be but by could did do down each ere every
        for from had has have he her him his how i if in into is it its like me more
        most much my no nor not now o of oh on one or our out own shall she so some
        still such than that the thee their them then there they this thou though
        through thus thy till tis to too up upon us was we were what when where which
        who whom whose will with would ye yet you your
        """.split()
    ),
    "persian": frozenset(
        """
        و که به است در از تو بر این آن را با من ما تا هر چون چه نه ای هم اگر یا یک
        بود شد شود کرد کند هست نیست بی گر ور کس کسی خود همه هیچ چند بس زان کان کز زین
        کین ز او وی شما باشد نمی می دگر دیگر بسی مگر پس چو همی اندر سوی روی ست اند
        """.split()
    ),
}

# Words joined by an apostrophe (scatter'd) or a zero-width non-joiner (Persian
# compounds) stay one token; hyphens split.
_TOKEN_RE = re.compile(r"[^\W\d_]+(?:['‌][^\W\d_]+)*")
_ARABIC_DIACRITICS_RE = re.compile(r"[ً-ٰٟ]")
_PERSIAN_CHAR_MAP = str.maketrans(
    {
        "ي": "ی",  # Arabic yeh  -> Persian yeh
        "ى": "ی",  # alef maksura -> Persian yeh
        "ك": "ک",  # Arabic kaf  -> Persian kaf
        "ـ": "",  # tatweel (kashida)
        "ۀ": "ه",  # heh with hamza above -> heh
    }
)
_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "ʼ": "'"})


def normalize(text: str, language: Language) -> str:
    """Return a canonical form of ``text`` for counting and matching.

    English is lower-cased with curly apostrophes straightened. Persian has
    Arabic-script variants of yeh/kaf folded to their Persian code points and
    short-vowel diacritics removed, which is how the raw XML varies.
    """
    text = unicodedata.normalize("NFC", text)
    if language == "english":
        return text.translate(_APOSTROPHES).lower()
    text = text.translate(_PERSIAN_CHAR_MAP)
    return _ARABIC_DIACRITICS_RE.sub("", text)


def tokenize(text: str, language: Language) -> list[str]:
    """Split ``text`` into normalised word tokens."""
    return _TOKEN_RE.findall(normalize(text, language))


@dataclass(frozen=True)
class Line:
    quatrain: int
    number: int  # 1-based position inside the quatrain
    text: str
    tokens: tuple[str, ...]
    indented: bool = False


@dataclass
class Corpus:
    language: Language
    path: Path
    quatrains: dict[int, list[Line]] = field(default_factory=dict)

    # ---- construction -------------------------------------------------
    @classmethod
    def load(cls, language: Language, path: Path) -> "Corpus":
        root = ET.parse(path).getroot()
        corpus = cls(language=language, path=path)
        for lg in root.iter():
            if _local(lg.tag) != "lg":
                continue
            n = int(lg.get("n"))
            lines: list[Line] = []
            for i, l in enumerate(e for e in lg if _local(e.tag) == "l"):
                text = (l.text or "").strip()
                lines.append(
                    Line(
                        quatrain=n,
                        number=i + 1,
                        text=text,
                        tokens=tuple(tokenize(text, language)),
                        indented=l.get("rend") == "indent",
                    )
                )
            corpus.quatrains[n] = lines
        corpus._index()
        return corpus

    def _index(self) -> None:
        self.term_counts: Counter[str] = Counter()
        self.quatrain_counts: Counter[str] = Counter()  # quatrains containing the word
        self.postings: dict[str, list[Line]] = {}
        for n, lines in self.quatrains.items():
            seen: set[str] = set()
            for line in lines:
                self.term_counts.update(line.tokens)
                for tok in set(line.tokens):  # one posting per line, however often the word recurs in it
                    self.postings.setdefault(tok, []).append(line)
                seen.update(line.tokens)
            for tok in seen:
                self.quatrain_counts[tok] += 1
        self.total_tokens = sum(self.term_counts.values())

    # ---- access --------------------------------------------------------
    @property
    def lines(self) -> Iterator[Line]:
        for n in sorted(self.quatrains):
            yield from self.quatrains[n]

    def quatrain(self, n: int) -> list[Line]:
        if n not in self.quatrains:
            raise KeyError(f"quatrain {n} not found; valid range is 1-{max(self.quatrains)}")
        return self.quatrains[n]

    def quatrain_text(self, n: int) -> str:
        return "\n".join(line.text for line in self.quatrain(n))

    # ---- statistics ----------------------------------------------------
    def frequency(
        self,
        *,
        top_n: int | None = 50,
        min_length: int = 1,
        min_count: int = 1,
        exclude_stopwords: bool = False,
        starts_with: str | None = None,
        contains: str | None = None,
    ) -> list[dict]:
        stop = STOPWORDS[self.language] if exclude_stopwords else frozenset()
        sw = normalize(starts_with, self.language) if starts_with else None
        ct = normalize(contains, self.language) if contains else None
        rows = [
            (word, count)
            for word, count in self.term_counts.most_common()
            if len(word) >= min_length
            and count >= min_count
            and word not in stop
            and (sw is None or word.startswith(sw))
            and (ct is None or ct in word)
        ]
        if top_n is not None:
            rows = rows[:top_n]
        return [
            {
                "rank": i + 1,
                "word": word,
                "count": count,
                "per_1000_tokens": round(count * 1000 / self.total_tokens, 2),
                "quatrains": self.quatrain_counts[word],
            }
            for i, (word, count) in enumerate(rows)
        ]

    def ngrams(
        self, n: int = 2, *, top_n: int | None = 30, exclude_stopwords: bool = False
    ) -> list[dict]:
        if n < 2:
            raise ValueError("n must be at least 2; use frequency() for single words")
        stop = STOPWORDS[self.language] if exclude_stopwords else frozenset()
        counts: Counter[tuple[str, ...]] = Counter()
        for line in self.lines:  # n-grams never cross a line break
            toks = line.tokens
            for i in range(len(toks) - n + 1):
                gram = toks[i:i + n]
                if any(t in stop for t in gram):
                    continue
                counts[gram] += 1
        rows = counts.most_common(top_n)
        return [
            {"rank": i + 1, "ngram": " ".join(gram), "count": count}
            for i, (gram, count) in enumerate(rows)
        ]

    def occurrences(self, word: str) -> list[Line]:
        return self.postings.get(normalize(word, self.language).strip(), [])

    def distribution(self, word: str) -> dict[int, int]:
        """Count of ``word`` in each quatrain where it appears."""
        dist: Counter[int] = Counter()
        key = normalize(word, self.language).strip()
        for line in self.postings.get(key, []):
            dist[line.quatrain] += line.tokens.count(key)
        return dict(sorted(dist.items()))

    def search(self, query: str, *, regex: bool = False, max_results: int | None = None) -> list[Line]:
        if regex:
            pattern = re.compile(query, re.IGNORECASE)
            hits = [line for line in self.lines if pattern.search(normalize(line.text, self.language))]
        else:
            q = normalize(query, self.language)
            hits = [line for line in self.lines if q in normalize(line.text, self.language)]
        return hits[:max_results] if max_results is not None else hits

    def summary(self) -> dict:
        return {
            "language": self.language,
            "file": self.path.name,
            "quatrains": len(self.quatrains),
            "lines": sum(len(v) for v in self.quatrains.values()),
            "tokens": self.total_tokens,
            "unique_words": len(self.term_counts),
            "hapax_legomena": sum(1 for c in self.term_counts.values() if c == 1),
        }


def _local(tag: str) -> str:
    """Strip an XML namespace prefix (``{ns}lg`` -> ``lg``)."""
    return tag.rsplit("}", 1)[-1]


def default_xml_dir() -> Path:
    """Directory holding the XML files: ``RUBAIYAT_XML_DIR`` or the repo root."""
    env = os.environ.get("RUBAIYAT_XML_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parent.parent


def load_corpora(xml_dir: Path | None = None, languages: Iterable[Language] = LANGUAGES) -> dict[Language, Corpus]:
    xml_dir = xml_dir or default_xml_dir()
    corpora: dict[Language, Corpus] = {}
    for lang in languages:
        path = xml_dir / FILES[lang]
        if not path.is_file():
            raise FileNotFoundError(f"{path} not found; set RUBAIYAT_XML_DIR to the directory holding the XML files")
        corpora[lang] = Corpus.load(lang, path)
    return corpora
