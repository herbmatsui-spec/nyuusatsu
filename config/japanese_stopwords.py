"""
Japanese stop words for TF-IDF vectorizer.

A lightweight stop word list tailored for Japanese bid specification texts.
These are high-frequency function words and boilerplate tokens that carry
little discriminative power for similarity matching of procurement documents.
"""

JAPANESE_STOP_WORDS: list[str] = [
    # Particles / auxiliary
    "の", "に", "は", "を", "た", "が", "で", "て", "と", "し", "れ",
    "も", "か", "ね", "よ", "さ", "ま", "も", "で", "て", "と",
    # Copula / desu-masu style
    "です", "ます", "です", "ます", "でし", "まし", "だ", "で", "ある",
    "いる", "ない", "無い", "有る", "無し", "する", "される", "できる",
    # Connectives
    "および", "及び", "または", "又は", "並びに", "ならびに", "そして",
    "また", "として", "により", "による", "ために", "ための",
    "において", "における", "について", "に対して", "に対する",
    "に関する", "に関して", "によれば", "によれて", "である", "であった",
    "という", "いう", "など", "等", "程度",
    # Demonstratives
    "この", "その", "あの", "これ", "それ", "あれ", "これら", "それら",
    "あれら", "このような", "そのような", "あのような",
    # Noun helpers
    "こと", "もの", "ため", "よう", "ところ", "様", "的", "化", "性",
    # Numbers / units commonly seen in specs (low discriminative power)
    "一", "二", "三", "四", "五", "六", "七", "八", "九", "十",
    "百", "千", "万", "円", "年", "月", "日",
]

# Deduplicate while preserving order
_seen: set[str] = set()
JAPANESE_STOP_WORDS = [w for w in JAPANESE_STOP_WORDS if not (w in _seen or _seen.add(w))]
