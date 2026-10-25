"""Vendored instruction_following_eval package."""

from pathlib import Path

import nltk

_NLTK_DATA = Path(__file__).parent / "nltk_data"
if _NLTK_DATA.exists() and str(_NLTK_DATA) not in nltk.data.path:
    nltk.data.path.insert(0, str(_NLTK_DATA))
