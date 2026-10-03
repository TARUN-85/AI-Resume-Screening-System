"""
TF-IDF based text similarity.

CONCEPTS (see docs/INTERVIEW_GUIDE.md for full explanations with numeric
examples):

- Term Frequency (TF): how often a term appears in a document, relative
  to the document's length.
- Inverse Document Frequency (IDF): down-weights terms that appear in
  many documents (e.g. "experience") and up-weights terms that are
  distinctive to few documents.
- TF-IDF = TF * IDF: a term is considered important if it is frequent in
  THIS document but rare ACROSS documents.
- Cosine similarity: measures the angle between two TF-IDF vectors,
  which captures how similar their *direction* (word usage pattern) is,
  independent of document length.

IMPORTANT LIMITATION (repeated intentionally so it is impossible to
miss): TF-IDF + cosine similarity is a LEXICAL similarity measure. It
compares surface-level word overlap. It does NOT understand meaning:
"machine learning" and "ML" are treated as unrelated unless the exact
tokens overlap, and it has no concept of synonyms. It is not a semantic
similarity measure like embeddings from a Sentence Transformer / BERT
would provide (see "Future Enhancements" in the README).
"""

from dataclasses import dataclass

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.utils.logger import get_logger

logger = get_logger(__name__)


class TfidfMatchError(Exception):
    """Raised when TF-IDF vectorization fails (e.g. empty vocabulary)."""


@dataclass
class TfidfMatchResult:
    similarity_score: float  # raw cosine similarity in [0, 1]
    similarity_percentage: float  # similarity_score * 100, rounded


def compute_text_similarity(jd_text: str, resume_text: str) -> TfidfMatchResult:
    """
    Vectorize the JD and resume text with TF-IDF and compute cosine
    similarity between the two resulting vectors.

    Both documents are vectorized together (fit_transform on a 2-document
    corpus) so that IDF weights are computed consistently across the pair.
    """
    if not jd_text.strip() or not resume_text.strip():
        raise TfidfMatchError("Cannot compute similarity on empty text.")

    vectorizer = TfidfVectorizer()
    try:
        tfidf_matrix = vectorizer.fit_transform([jd_text, resume_text])
    except ValueError as exc:
        # scikit-learn raises ValueError when the resulting vocabulary is
        # empty (e.g. both documents contained only stopwords/punctuation).
        raise TfidfMatchError(
            "TF-IDF vocabulary is empty -- documents contained no usable terms."
        ) from exc

    if tfidf_matrix.shape[1] == 0:
        raise TfidfMatchError("TF-IDF vocabulary is empty.")

    similarity_matrix = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])
    raw_score = float(similarity_matrix[0][0])
    raw_score = max(0.0, min(1.0, raw_score))  # guard against float drift

    logger.info("Computed TF-IDF cosine similarity: %.4f", raw_score)

    return TfidfMatchResult(
        similarity_score=raw_score,
        similarity_percentage=round(raw_score * 100, 2),
    )
