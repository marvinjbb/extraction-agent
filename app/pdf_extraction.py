from dataclasses import dataclass
from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PyPdfError


class PDFExtractionError(Exception):
    """Raised when a PDF cannot be read safely by the extraction layer."""


class NoExtractableTextError(PDFExtractionError):
    """Raised when a readable PDF contains no embedded text."""


@dataclass(frozen=True)
class ExtractedPDFText:
    """Page count and combined text extracted from a PDF."""

    page_count: int
    text: str


def extract_pdf_text(pdf_bytes: bytes) -> ExtractedPDFText:
    """Extract and combine embedded text from an in-memory PDF."""
    try:
        reader = PdfReader(BytesIO(pdf_bytes))

        if reader.is_encrypted:
            raise PDFExtractionError("Password-protected PDFs are not supported.")

        page_text = [(page.extract_text() or "").strip() for page in reader.pages]
    except PDFExtractionError:
        raise
    except (PyPdfError, OSError, ValueError) as exc:
        raise PDFExtractionError("The uploaded PDF could not be read.") from exc

    readable_pages = [text for text in page_text if text]
    if not readable_pages:
        raise NoExtractableTextError(
            "The uploaded PDF contains no extractable text. OCR is not supported."
        )

    return ExtractedPDFText(
        page_count=len(reader.pages),
        text="\n\n".join(readable_pages),
    )
