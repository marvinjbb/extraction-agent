"""Run one content-free Structured Outputs diagnostic against synthetic input."""

import asyncio
import json
import os
from importlib.metadata import version

from openai import AsyncOpenAI

from app.llm_extraction import (
    DEFAULT_MODEL,
    INVOICE_EXTRACTION_INSTRUCTIONS,
    INVOICE_MAX_OUTPUT_TOKENS,
    describe_provider_response,
)
from app.schemas import Invoice

SYNTHETIC_INVOICE = (
    "SYNTHETIC SAMPLE INVOICE - NOT A REAL TRANSACTION; "
    "Vendor: Example Test Supplies; Invoice Number: SYN-2026-0916; "
    "Invoice Date: 2026-09-16; Currency: USD; Subtotal: 100.00; "
    "Tax: 8.25; Total: 108.25"
)


async def main() -> None:
    """Print only allowlisted structural metadata about one provider response."""
    model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
    timeout = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "30"))
    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"], timeout=timeout)
    response = await client.responses.parse(
        model=model,
        input=[
            {"role": "developer", "content": INVOICE_EXTRACTION_INSTRUCTIONS},
            {"role": "user", "content": SYNTHETIC_INVOICE},
        ],
        text_format=Invoice,
        max_output_tokens=INVOICE_MAX_OUTPUT_TOKENS,
    )
    diagnostic = {
        "openai_sdk_version": version("openai"),
        "configured_model": model,
        "response": describe_provider_response(response).as_safe_dict(),
    }
    print(json.dumps(diagnostic, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
