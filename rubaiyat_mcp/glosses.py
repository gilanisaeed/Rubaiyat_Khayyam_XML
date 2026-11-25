"""English summaries, tags and curated correspondences for every quatrain.

Loaded from ``glosses.json`` next to this module. Glosses let a paraphrased
English query ("not fearing death") reach quatrains that use none of its
words, in either language. ``related`` records which Persian quatrains an
English one draws on; the reverse direction is derived.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from rubaiyat_mcp.corpus import Language, tokenize

_PATH = Path(__file__).with_name("glosses.json")


@dataclass(frozen=True)
class Gloss:
    language: Language
    quatrain: int
    gloss: str
    tags: tuple[str, ...]
    related: tuple[int, ...]  # quatrain numbers in the other language
    tokens: Counter = field(default_factory=Counter, compare=False)


class Glossary:
    def __init__(self, data: dict) -> None:
        self._by_key: dict[tuple[str, int], Gloss] = {}
        english = data["english"]
        persian = data["persian"]
        inverse: dict[int, list[int]] = {}
        for n, entry in english.items():
            for m in entry.get("related", []):
                inverse.setdefault(int(m), []).append(int(n))
        for lang, table in (("english", english), ("persian", persian)):
            for n, entry in table.items():
                num = int(n)
                related = entry.get("related", []) if lang == "english" else sorted(inverse.get(num, []))
                tokens = Counter(tokenize(entry["gloss"], "english"))
                for tag in entry["tags"]:
                    tokens.update(tokenize(tag, "english"))
                self._by_key[(lang, num)] = Gloss(
                    language=lang,  # type: ignore[arg-type]
                    quatrain=num,
                    gloss=entry["gloss"],
                    tags=tuple(entry["tags"]),
                    related=tuple(int(r) for r in related),
                    tokens=tokens,
                )

    @classmethod
    def load(cls, path: Path = _PATH) -> "Glossary":
        with path.open(encoding="utf-8") as fh:
            return cls(json.load(fh))

    def get(self, language: str, n: int) -> Gloss:
        return self._by_key[(language, n)]

    def match(self, language: str, words: list[str]) -> dict[int, dict]:
        """Score quatrains of ``language`` by gloss/tag hits for English ``words``.

        Returns ``{n: {"score": hits, "matched_words": [...]}}`` for quatrains
        with at least one hit. A query equal to a whole tag counts extra.
        """
        keys = [k for w in words for k in tokenize(w, "english")]
        phrase = " ".join(words).lower().strip()
        hits: dict[int, dict] = {}
        for (lang, n), g in self._by_key.items():
            if lang != language:
                continue
            score = 0
            matched: list[str] = []
            for k in keys:
                c = g.tokens.get(k, 0)
                if c:
                    score += c
                    if k not in matched:
                        matched.append(k)
            if phrase and phrase in (t.lower() for t in g.tags):
                score += 2
                if phrase not in matched:
                    matched.append(phrase)
            if score:
                hits[n] = {"score": score, "matched_words": matched}
        return hits
