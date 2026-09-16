from app.image_processing import prepare_uploaded_image, render_pdf_for_vision
from app.llm_extraction import InvoiceExtractor, VisionInvoiceExtractor
from app.observability import log_event
from app.pdf_extraction import NoExtractableTextError, extract_pdf_text
from app.schemas import Invoice
from app.upload_validation import InvoiceMediaType, ValidatedInvoiceUpload


class InvoiceExtractionWorkflow:
    """Route validated media through text-first or vision invoice extraction."""

    def __init__(
        self,
        text_extractor: InvoiceExtractor,
        vision_extractor: VisionInvoiceExtractor,
    ) -> None:
        self._text_extractor = text_extractor
        self._vision_extractor = vision_extractor

    async def extract(self, upload: ValidatedInvoiceUpload) -> Invoice:
        if upload.media_type is InvoiceMediaType.PDF:
            try:
                extracted = extract_pdf_text(upload.content)
            except NoExtractableTextError:
                log_event(
                    "extraction_path_selected",
                    extraction_path="vision_scanned_pdf",
                    media_type=upload.media_type.value,
                )
                images = render_pdf_for_vision(upload.content)
                return await self._vision_extractor.extract_images(images)
            log_event(
                "extraction_path_selected",
                extraction_path="embedded_pdf_text",
                media_type=upload.media_type.value,
            )
            return await self._text_extractor.extract(extracted.text)

        log_event(
            "extraction_path_selected",
            extraction_path="vision_image",
            media_type=upload.media_type.value,
        )
        image = prepare_uploaded_image(upload.content, upload.media_type)
        return await self._vision_extractor.extract_images([image])
