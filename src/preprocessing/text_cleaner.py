"""
Text preprocessing pipeline for the AI Resume Screening System.

DESIGN DECISION -- why we do NOT strip all "special characters":
------------------------------------------------------------------
A naive preprocessing pipeline strips every non-alphanumeric character.
That would silently destroy technology names that rely on punctuation
for their meaning, e.g.:

    C++      -> "C" (loses all meaning -- becomes the letter grade "C")
    C#       -> "C"
    .NET     -> "NET" (loses the leading dot that identifies the framework)
    Node.js  -> "Node js" (arguably still recoverable, but inconsistent)
    scikit-learn -> "scikit learn" (hyphen is meaningful in the skill name)

Because this system's entire value proposition is *accurate, explainable
skill matching*, silently mangling technology names would directly hurt
skill extraction. So instead of a blanket "remove all punctuation" step,
we:

    1. Protect a small set of known "special" technology tokens by
       temporarily replacing them with placeholder tokens before
       cleaning.
    2. Run the standard cleaning pipeline (lowercase, punctuation
       removal, whitespace normalization, tokenization, stopword
       removal, optional lemmatization).
    3. Restore the protected tokens afterward.

This keeps the pipeline simple and fully rule-based (no external NER
model needed) while still preserving the technology names that matter
for scoring.
"""

import re
from dataclasses import dataclass, field

# Technology tokens whose punctuation is semantically meaningful.
# Longest-first so "scikit-learn" is matched before any partial overlap.
_PROTECTED_TOKENS = [
    "scikit-learn", "c++", "c#", ".net", "node.js", "power bi",
    "ci/cd", "a/b testing",
]

_PLACEHOLDER_PREFIX = "__PROTECTED_TOKEN_"

# A small, standard English stopword list. Kept local (no NLTK download
# required) so the project has zero network dependency at run time.
STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "so", "of",
    "to", "in", "on", "at", "for", "with", "as", "by", "is", "are",
    "was", "were", "be", "been", "being", "this", "that", "these",
    "those", "it", "its", "we", "you", "your", "our", "they", "their",
    "i", "he", "she", "his", "her", "them", "will", "would", "can",
    "could", "should", "may", "might", "must", "shall", "do", "does",
    "did", "have", "has", "had", "not", "no", "nor", "from", "into",
    "about", "than", "too", "very", "just", "also",
}

# Simple lemmatization: rule-based suffix stripping for common plural /
# gerund / past-tense forms. This is intentionally lightweight (no
# external dependency like spaCy/NLTK WordNet) and is applied only as an
# *optional* step, since aggressive stemming can distort technical terms
# (e.g. we must NOT turn "iOS" into "iO").
_LEMMA_RULES = [
    (re.compile(r"(ing)$"), ""),
    (re.compile(r"(ed)$"), ""),
    (re.compile(r"(ies)$"), "y"),
    (re.compile(r"(es)$"), ""),
    (re.compile(r"(s)$"), ""),
]

# Do not lemmatize short tokens or known technical acronyms/skills --
# stripping "s" from "aws" or "ies" from something like "sql" would
# corrupt them.
_LEMMA_EXCLUDE = {
    "aws", "sql", "nlp", "gcp", "sas", "iis", "aas", "css", "js",
}


@dataclass
class CleanedText:
    """Result of running the preprocessing pipeline on one document."""

    raw_text: str
    cleaned_text: str
    tokens: list[str] = field(default_factory=list)


def _protect_special_tokens(text: str) -> tuple[str, dict[str, str]]:
    """Replace known punctuation-sensitive tokens with safe placeholders."""
    mapping: dict[str, str] = {}
    protected = text
    for idx, token in enumerate(_PROTECTED_TOKENS):
        pattern = re.compile(re.escape(token), re.IGNORECASE)
        if pattern.search(protected):
            placeholder = f"{_PLACEHOLDER_PREFIX}{idx}__"
            # Store the mapping key in lowercase because the placeholder
            # text passes through lowercase() later in the pipeline --
            # the lookup in _restore_special_tokens must match on the
            # same casing it will actually see.
            mapping[placeholder.lower()] = token.lower()
            protected = pattern.sub(f" {placeholder} ", protected)
    return protected, mapping


def _restore_special_tokens(tokens: list[str], mapping: dict[str, str]) -> list[str]:
    restored = []
    for tok in tokens:
        key = tok.strip().lower()
        if key in mapping:
            restored.append(mapping[key])
        else:
            restored.append(tok)
    return restored


def lowercase(text: str) -> str:
    return text.lower()


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def remove_punctuation(text: str) -> str:
    """Remove punctuation EXCEPT characters already protected upstream."""
    # Keep alphanumerics, whitespace, and the underscore used in our
    # placeholder tokens; drop everything else.
    return re.sub(r"[^a-z0-9_\s]", " ", text)


def tokenize(text: str) -> list[str]:
    return [t for t in text.split() if t]


def remove_stopwords(tokens: list[str]) -> list[str]:
    return [t for t in tokens if t not in STOPWORDS]


def lemmatize(tokens: list[str]) -> list[str]:
    lemmatized = []
    for tok in tokens:
        if tok in _LEMMA_EXCLUDE or tok.startswith(_PLACEHOLDER_PREFIX.lower()) or len(tok) <= 3:
            lemmatized.append(tok)
            continue
        new_tok = tok
        for pattern, repl in _LEMMA_RULES:
            if pattern.search(new_tok):
                new_tok = pattern.sub(repl, new_tok)
                break
        lemmatized.append(new_tok)
    return lemmatized


def clean_text(
    text: str,
    remove_stop: bool = True,
    apply_lemmatization: bool = False,
) -> CleanedText:
    """
    Run the full preprocessing pipeline on a piece of text.

    Steps: protect technology tokens -> lowercase -> remove punctuation
    -> normalize whitespace -> tokenize -> (optional) remove stopwords
    -> (optional) lemmatize -> restore technology tokens.
    """
    if not text or not text.strip():
        return CleanedText(raw_text=text, cleaned_text="", tokens=[])

    protected_text, mapping = _protect_special_tokens(text)
    lowered = lowercase(protected_text)
    no_punct = remove_punctuation(lowered)
    normalized = normalize_whitespace(no_punct)
    tokens = tokenize(normalized)

    if remove_stop:
        tokens = remove_stopwords(tokens)
    if apply_lemmatization:
        tokens = lemmatize(tokens)

    tokens = _restore_special_tokens(tokens, mapping)
    cleaned_text = " ".join(tokens)

    return CleanedText(raw_text=text, cleaned_text=cleaned_text, tokens=tokens)
