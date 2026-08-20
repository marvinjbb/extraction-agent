from io import BytesIO


def build_pdf(*page_texts: str | None) -> bytes:
    """Build a minimal test PDF with optional embedded text on each page."""
    font_object_number = 3 + (2 * len(page_texts))
    page_object_numbers = [3 + (2 * index) for index in range(len(page_texts))]

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        (
            f"<< /Type /Pages /Kids "
            f"[{' '.join(f'{number} 0 R' for number in page_object_numbers)}] "
            f"/Count {len(page_texts)} >>"
        ).encode(),
    ]

    for index, text in enumerate(page_texts):
        content_object_number = page_object_numbers[index] + 1
        page = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 {font_object_number} 0 R >> >> "
            f"/Contents {content_object_number} 0 R >>"
        ).encode()
        objects.append(page)

        escaped_text = (text or "").replace("\\", "\\\\").replace("(", "\\(")
        escaped_text = escaped_text.replace(")", "\\)")
        stream = (
            f"BT /F1 12 Tf 72 720 Td ({escaped_text}) Tj ET".encode() if text else b""
        )
        objects.append(
            b"<< /Length "
            + str(len(stream)).encode()
            + b" >>\nstream\n"
            + stream
            + b"\nendstream"
        )

    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    output = BytesIO()
    output.write(b"%PDF-1.4\n")
    offsets = [0]

    for number, body in enumerate(objects, start=1):
        offsets.append(output.tell())
        output.write(f"{number} 0 obj\n".encode())
        output.write(body)
        output.write(b"\nendobj\n")

    xref_offset = output.tell()
    output.write(f"xref\n0 {len(objects) + 1}\n".encode())
    output.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.write(f"{offset:010d} 00000 n \n".encode())

    output.write(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode()
    )
    return output.getvalue()
