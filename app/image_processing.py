import warnings
from dataclasses import dataclass
from io import BytesIO

import pymupdf
from PIL import Image, ImageOps, UnidentifiedImageError

from app.pdf_extraction import PDFExtractionError
from app.upload_validation import InvoiceMediaType

MAX_IMAGE_PIXELS = 20_000_000
MAX_IMAGE_DIMENSION = 2_000
MAX_VISION_PDF_PAGES = 5


class ImageProcessingError(Exception):
    """Raised when image content cannot be processed within MVP safety limits."""


@dataclass(frozen=True)
class InvoiceImage:
    """A normalized image safe to pass across the vision-provider boundary."""

    content: bytes
    media_type: str = "image/jpeg"


def prepare_uploaded_image(
    image_bytes: bytes, declared_type: InvoiceMediaType
) -> InvoiceImage:
    """Decode, verify, orient, bound, and normalize one uploaded invoice image."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(image_bytes)) as source:
                if getattr(source, "n_frames", 1) != 1:
                    raise ImageProcessingError(
                        "Animated or multi-frame invoice images are not supported."
                    )
                expected_format = {
                    InvoiceMediaType.JPEG: "JPEG",
                    InvoiceMediaType.PNG: "PNG",
                }[declared_type]
                if source.format != expected_format:
                    raise ImageProcessingError(
                        "The uploaded image content does not match its declared format."
                    )
                width, height = source.size
                if width * height > MAX_IMAGE_PIXELS:
                    raise ImageProcessingError(
                        "The uploaded image exceeds the 20 megapixel safety limit."
                    )
                source.load()
                normalized = ImageOps.exif_transpose(source).convert("RGB")
    except ImageProcessingError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ImageProcessingError(
            "The uploaded image exceeds the 20 megapixel safety limit."
        ) from exc
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ImageProcessingError("The uploaded image could not be read.") from exc

    normalized.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION))
    output = BytesIO()
    normalized.save(output, format="JPEG", quality=90, optimize=True)
    return InvoiceImage(content=output.getvalue())


def render_pdf_for_vision(pdf_bytes: bytes) -> list[InvoiceImage]:
    """Render a bounded scanned PDF into normalized page images."""
    try:
        document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        if document.needs_pass:
            raise PDFExtractionError("Password-protected PDFs are not supported.")
        if document.page_count == 0:
            raise PDFExtractionError("The uploaded PDF contains no pages.")
        if document.page_count > MAX_VISION_PDF_PAGES:
            raise ImageProcessingError(
                "Scanned PDFs are limited to 5 pages in this demo."
            )

        images: list[InvoiceImage] = []
        for page in document:
            rectangle = page.rect
            longest_side = max(rectangle.width, rectangle.height)
            scale = min(MAX_IMAGE_DIMENSION / longest_side, 2.0)
            pixmap = page.get_pixmap(
                matrix=pymupdf.Matrix(scale, scale),
                colorspace=pymupdf.csRGB,
                alpha=False,
            )
            images.append(
                InvoiceImage(
                    content=pixmap.tobytes("jpeg", jpg_quality=90),
                )
            )
        return images
    except (ImageProcessingError, PDFExtractionError):
        raise
    except (pymupdf.FileDataError, RuntimeError, ValueError) as exc:
        raise PDFExtractionError("The uploaded PDF could not be rendered.") from exc
    finally:
        if "document" in locals():
            document.close()
