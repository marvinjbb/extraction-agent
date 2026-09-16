from io import BytesIO

import pytest
from PIL import Image

from app.image_processing import (
    ImageProcessingError,
    prepare_uploaded_image,
    render_pdf_for_vision,
)
from app.pdf_extraction import PDFExtractionError
from app.upload_validation import InvoiceMediaType
from tests.pdf_factory import build_pdf


def build_image(image_format: str, size: tuple[int, int] = (400, 600)) -> bytes:
    image = Image.new("RGB", size, "white")
    output = BytesIO()
    image.save(output, format=image_format)
    return output.getvalue()


@pytest.mark.parametrize(
    ("image_format", "media_type"),
    [("JPEG", InvoiceMediaType.JPEG), ("PNG", InvoiceMediaType.PNG)],
)
def test_uploaded_image_is_normalized_for_vision(
    image_format: str, media_type: InvoiceMediaType
) -> None:
    result = prepare_uploaded_image(build_image(image_format), media_type)

    assert result.media_type == "image/jpeg"
    with Image.open(BytesIO(result.content)) as normalized:
        assert normalized.format == "JPEG"
        assert normalized.size == (400, 600)


def test_declared_image_type_must_match_decoded_format() -> None:
    with pytest.raises(ImageProcessingError, match="declared format"):
        prepare_uploaded_image(build_image("PNG"), InvoiceMediaType.JPEG)


def test_multi_frame_image_is_rejected() -> None:
    output = BytesIO()
    first = Image.new("RGB", (20, 20), "white")
    second = Image.new("RGB", (20, 20), "black")
    first.save(output, format="PNG", save_all=True, append_images=[second])

    with pytest.raises(ImageProcessingError, match="multi-frame"):
        prepare_uploaded_image(output.getvalue(), InvoiceMediaType.PNG)


def test_large_dimension_is_normalized_without_distortion() -> None:
    result = prepare_uploaded_image(
        build_image("PNG", (4000, 1000)), InvoiceMediaType.PNG
    )

    with Image.open(BytesIO(result.content)) as normalized:
        assert normalized.size == (2000, 500)


def test_decoded_image_pixel_limit_is_enforced(monkeypatch) -> None:
    monkeypatch.setattr("app.image_processing.MAX_IMAGE_PIXELS", 100)

    with pytest.raises(ImageProcessingError, match="20 megapixel"):
        prepare_uploaded_image(build_image("PNG", (11, 10)), InvoiceMediaType.PNG)


def test_scanned_pdf_pages_are_rendered_for_vision() -> None:
    images = render_pdf_for_vision(build_pdf(None, None))

    assert len(images) == 2
    assert all(image.media_type == "image/jpeg" for image in images)
    assert all(image.content.startswith(b"\xff\xd8\xff") for image in images)


def test_scanned_pdf_page_limit_is_enforced() -> None:
    with pytest.raises(ImageProcessingError, match="limited to 5 pages"):
        render_pdf_for_vision(build_pdf(*([None] * 6)))


def test_empty_pdf_is_rejected() -> None:
    with pytest.raises(PDFExtractionError, match="contains no pages"):
        render_pdf_for_vision(build_pdf())
