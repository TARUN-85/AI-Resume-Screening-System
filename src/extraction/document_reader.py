"""
Document reader abstraction.

Today the system only supports TXT files. However, PDF and DOCX are
common resume formats, so the reading logic is placed behind a small
interface (DocumentReader) with one concrete implementation
(TxtDocumentReader). Adding PDF/DOCX support later means writing a new
class that implements `read(path) -> str` and registering it in
`get_reader_for(path)` -- no other code in the system needs to change.

Future extensions (not implemented here, left as an exercise):
    class PdfDocumentReader(DocumentReader):
        def read(self, path: Path) -> str:
            from pypdf import PdfReader
            ...

    class DocxDocumentReader(DocumentReader):
        def read(self, path: Path) -> str:
            import docx
            ...
"""

from abc import ABC, abstractmethod
from pathlib import Path

from src.utils.logger import get_logger

logger = get_logger(__name__)


class DocumentReadError(Exception):
    """Raised when a document cannot be read or is invalid."""


class DocumentReader(ABC):
    """Interface every concrete document reader must implement."""

    @abstractmethod
    def read(self, path: Path) -> str:
        """Read a document at `path` and return its raw text content."""
        raise NotImplementedError


class TxtDocumentReader(DocumentReader):
    """Reads plain-text (.txt) files."""

    def read(self, path: Path) -> str:
        if not path.exists():
            raise DocumentReadError(f"File not found: {path}")
        if path.suffix.lower() != ".txt":
            raise DocumentReadError(
                f"TxtDocumentReader only supports .txt files, got: {path.suffix}"
            )
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise DocumentReadError(f"Could not decode file as UTF-8: {path}") from exc

        if not text or not text.strip():
            raise DocumentReadError(f"File is empty: {path}")

        logger.info("Read file '%s' (%d characters)", path.name, len(text))
        return text


# Registry mapping file extensions to reader instances. This is the one
# place to update when PDF/DOCX readers are added.
_READERS: dict[str, DocumentReader] = {
    ".txt": TxtDocumentReader(),
}


def get_reader_for(path: Path) -> DocumentReader:
    """Return the appropriate DocumentReader for a given file path."""
    ext = path.suffix.lower()
    reader = _READERS.get(ext)
    if reader is None:
        raise DocumentReadError(
            f"Unsupported file type '{ext}'. Supported types: {list(_READERS.keys())}"
        )
    return reader


def read_document(path: Path) -> str:
    """Convenience function: read any supported document by path."""
    reader = get_reader_for(path)
    return reader.read(path)
