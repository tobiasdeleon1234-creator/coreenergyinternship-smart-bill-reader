import asyncio
import base64
import json
import os
from typing import Any

import httpx

from app.models import BillExtraction


GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions"

EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "is_bill_or_invoice": {
            "type": "boolean",
            "description": "True only when the uploaded document is clearly a utility bill, invoice, or receipt-like billing document.",
        },
        "validation_reason": {
            "type": "string",
            "description": "Short explanation of why the document was accepted or rejected.",
        },
        "vendor_name": {
            "type": ["string", "null"],
            "description": "Company, utility provider, merchant, or issuer name exactly as shown. Null if not visible.",
        },
        "invoice_date": {
            "type": ["string", "null"],
            "description": "Invoice or bill date in YYYY-MM-DD format when reliably determined. Null if absent or ambiguous.",
        },
        "total_amount": {
            "type": ["number", "null"],
            "description": "Final amount due/payable as a number only. Do not include a currency symbol. Null if not visible.",
        },
        "tax_amount": {
            "type": ["number", "null"],
            "description": "Explicit tax/VAT amount as a number only. Do not calculate tax if it is not explicitly shown.",
        },
        "line_items": {
            "type": "array",
            "description": "Itemized charges shown on the bill. Do not invent items.",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "amount": {"type": ["number", "null"]},
                },
                "required": ["description", "amount"],
                "additionalProperties": False,
            },
        },
        "estimated_confidence": {
            "type": "object",
            "description": "Model-estimated confidence from 0.0 to 1.0 based only on readability and clarity of the document. This is not a calibrated API confidence score.",
            "properties": {
                "vendor_name": {"type": "number", "minimum": 0, "maximum": 1},
                "invoice_date": {"type": "number", "minimum": 0, "maximum": 1},
                "total_amount": {"type": "number", "minimum": 0, "maximum": 1},
                "tax_amount": {"type": "number", "minimum": 0, "maximum": 1},
                "line_items": {"type": "number", "minimum": 0, "maximum": 1},
            },
            "required": ["vendor_name", "invoice_date", "total_amount", "tax_amount", "line_items"],
            "additionalProperties": False,
        },
    },
    "required": [
        "is_bill_or_invoice",
        "validation_reason",
        "vendor_name",
        "invoice_date",
        "total_amount",
        "tax_amount",
        "line_items",
        "estimated_confidence",
    ],
    "additionalProperties": False,
}

PROMPT = """
You are a careful bill and invoice data-extraction system.

Inspect ONLY the uploaded document and return structured data that matches the supplied JSON schema.

Rules:
1. First decide whether the document is actually a utility bill, invoice, or receipt-like billing document.
2. Never invent, estimate, or fill in a value that is not visible. Use null when a field cannot be read reliably.
3. vendor_name: use the issuer/provider/merchant name, not the customer's name.
4. invoice_date: use the invoice/bill/statement date, not the due date, payment date, or service-period date. Normalize to YYYY-MM-DD only when reliable.
5. total_amount: use the final total or amount due/payable. Return a numeric value without commas or currency symbols.
6. tax_amount: extract only an explicitly shown tax/VAT amount. Do NOT derive it from a percentage.
7. line_items: include individual billed products/services/charges and their amounts. Exclude subtotals, tax lines, discounts, previous balances, and grand total unless they are the only itemized charges shown.
8. Preserve negative amounts when the document shows credits or discounts as negatives.
9. If the document is clearly not a bill/invoice/receipt, set is_bill_or_invoice=false and keep unavailable extraction fields null or empty.
10. estimated_confidence is your own readability-based estimate from 0.0 to 1.0; it is not a calibrated API confidence score.
""".strip()


def _extract_output_text(payload: dict[str, Any]) -> str:
    """Extract text from the REST Interactions API response."""
    for step in reversed(payload.get("steps", [])):
        if step.get("type") != "model_output":
            continue
        texts = [
            item.get("text", "")
            for item in step.get("content", [])
            if item.get("type") == "text"
        ]
        if texts:
            return "".join(texts)
    raise ValueError("The AI response did not contain text output.")


async def extract_bill(file_bytes: bytes, mime_type: str) -> BillExtraction:
    api_key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured on the server.")

    media_type = "document" if mime_type == "application/pdf" else "image"
    encoded = base64.b64encode(file_bytes).decode("utf-8")

    request_body = {
        "model": model,
        "input": [
            {
                "type": media_type,
                "data": encoded,
                "mime_type": mime_type,
            },
            {"type": "text", "text": PROMPT},
        ],
        "response_format": {
            "type": "text",
            "mime_type": "application/json",
            "schema": EXTRACTION_SCHEMA,
        },
        "generation_config": {
            "max_output_tokens": 2500,
        },
    }

    headers = {
        "x-goog-api-key": api_key,
        "Content-Type": "application/json",
        "Api-Revision": "2026-05-20",
    }

    retryable_statuses = {429, 500, 502, 503, 504}
    max_attempts = 3

    async with httpx.AsyncClient(timeout=75.0) as client:
        for attempt in range(1, max_attempts + 1):
            try:
                response = await client.post(
                    GEMINI_ENDPOINT,
                    headers=headers,
                    json=request_body,
                )
            except httpx.RequestError as exc:
                if attempt == max_attempts:
                    raise RuntimeError(
                        "Gemini API request failed after multiple attempts."
                    ) from exc

                await asyncio.sleep(2 ** (attempt - 1))
                continue

            if response.status_code < 400:
                break

            try:
                detail = response.json().get("error", {}).get(
                    "message", response.text
                )
            except Exception:
                detail = response.text

            if (
                response.status_code not in retryable_statuses
                or attempt == max_attempts
            ):
                raise RuntimeError(
                    f"Gemini API error ({response.status_code}): {detail}"
                )

            await asyncio.sleep(2 ** (attempt - 1))

    payload = response.json()

    if payload.get("status") not in (None, "completed"):
        raise RuntimeError(
            f"AI processing did not complete successfully "
            f"(status: {payload.get('status')})."
        )

    output_text = _extract_output_text(payload)
    parsed = json.loads(output_text)

    return BillExtraction.model_validate(parsed)