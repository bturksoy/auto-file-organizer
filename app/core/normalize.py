"""Text normalization shared by filename matching and content scanning."""
from __future__ import annotations

import re
import unicodedata


def normalize(s: str) -> str:
    """Case-fold, strip diacritics, fold Turkish dotless ı to i."""
    s = unicodedata.normalize("NFD", s.casefold())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.replace("ı", "i")


def maybe_despace(text: str) -> str:
    """Repair PDF text rendered character-by-character.

    Some PDFs (Canva, Figma, etc.) place each glyph as its own text object
    and most extractors then emit one space between every character:
    ``W o r k  E x p e r i e n c e``. If most tokens are single chars we
    collapse the inter-character spaces while preserving word breaks
    (which appear as double spaces in this layout).
    """
    tokens = text.split()
    if len(tokens) < 10:
        return text
    single = sum(1 for tok in tokens if len(tok) == 1) / len(tokens)
    if single < 0.4:
        return text
    placeholder = "\x00"
    out = re.sub(r"  +", placeholder, text)
    out = out.replace(" ", "")
    return out.replace(placeholder, " ")


def aggressive_strip(s: str) -> str:
    """Drop all whitespace + control bytes (used for fuzzy comparisons)."""
    return re.sub(r"[\s\x00-\x1f]+", "", s)
