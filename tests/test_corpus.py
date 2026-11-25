"""Tests for corpus parsing, normalisation and frequency helpers."""

import pytest

from rubaiyat_mcp.corpus import STOPWORDS, load_corpora, normalize, tokenize


@pytest.fixture(scope="module")
def corpora():
    return load_corpora()


def test_both_corpora_have_75_aligned_quatrains(corpora):
    for c in corpora.values():
        assert sorted(c.quatrains) == list(range(1, 76))
        assert all(len(lines) == 4 for lines in c.quatrains.values())


def test_english_tokenizer_keeps_apostrophe_contractions():
    assert tokenize("WAKE! For the Sun, who scatter'd into flight", "english") == [
        "wake", "for", "the", "sun", "who", "scatter'd", "into", "flight",
    ]
    assert tokenize("Jamshyd's Sev'n-ring'd Cup", "english") == ["jamshyd's", "sev'n", "ring'd", "cup"]


def test_persian_normalisation_folds_arabic_yeh_and_kaf_and_strips_diacritics():
    # The XML uses Arabic yeh (U+064A); users typically type Persian yeh (U+06CC).
    assert normalize("مي", "persian") == normalize("می", "persian") == "می"
    assert normalize("كه", "persian") == "که"
    assert normalize("ِتوست", "persian") == "توست"


def test_frequency_top_word(corpora):
    en = corpora["english"].frequency(top_n=1)[0]
    assert en["word"] == "the" and en["count"] == 173
    fa = corpora["persian"].frequency(top_n=1)[0]
    assert fa["word"] == "و" and fa["count"] == 82


def test_frequency_excludes_stopwords(corpora):
    rows = corpora["english"].frequency(top_n=20, exclude_stopwords=True)
    assert all(r["word"] not in STOPWORDS["english"] for r in rows)
    assert rows[0]["word"] == "wine"


def test_persian_stopwords_match_normalised_tokens(corpora):
    # Every stopword must itself be in normalised form, or it would never match.
    for word in STOPWORDS["persian"]:
        assert normalize(word, "persian") == word


def test_occurrences_match_whole_tokens_either_spelling(corpora):
    fa = corpora["persian"]
    arabic_yeh = fa.occurrences("مي")
    persian_yeh = fa.occurrences("می")
    assert arabic_yeh and arabic_yeh == persian_yeh
    en = corpora["english"]
    assert all("wine" in line.tokens for line in en.occurrences("Wine"))
    assert en.occurrences("win") == []


def test_distribution_sums_to_count(corpora):
    en = corpora["english"]
    dist = en.distribution("wine")
    assert sum(dist.values()) == en.term_counts["wine"] == 11
    assert len(dist) == en.quatrain_counts["wine"]
    assert dist[6] == 4  # 'Wine! Wine! Wine!' + 'Red Wine!' - repeats inside a line count once each


def test_occurrences_lists_each_line_once(corpora):
    en = corpora["english"]
    lines = en.occurrences("wine")
    assert len(lines) == len({(line.quatrain, line.number) for line in lines})


def test_search_substring_and_regex(corpora):
    en = corpora["english"]
    assert any("Nightingale" in line.text for line in en.search("nightingale"))
    assert len(en.search(r"^the \w+ of", regex=True)) >= 1


def test_ngrams(corpora):
    rows = corpora["english"].ngrams(2, top_n=5)
    assert rows[0]["rank"] == 1 and " " in rows[0]["ngram"]
    with pytest.raises(ValueError):
        corpora["english"].ngrams(1)


def test_missing_quatrain_raises(corpora):
    with pytest.raises(KeyError):
        corpora["english"].quatrain(76)


def test_load_from_explicit_directory(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_corpora(tmp_path)


def test_summary_fields(corpora):
    s = corpora["english"].summary()
    assert s["quatrains"] == 75 and s["lines"] == 300 and s["tokens"] > 2000
