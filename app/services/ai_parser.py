import anthropic
import openai
import json
from pydantic import BaseModel, ValidationError
from typing import Literal
from app.core.config import settings

client_anthropic = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
client_openai = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

PDF_EXTRACTION_PROMPT = """
You are a financial data extraction engine. Extract ALL transactions from this
bank statement. Return ONLY a valid JSON array — no preamble, no markdown fences.

Schema for each transaction:
{
  "date": "YYYY-MM-DD",
  "description": "merchant or narration as written",
  "amount": 1234.56,
  "type": "credit" | "debit",
  "balance_after": 5000.00 | null,
  "reference": "string or null"
}

Rules:
- amount is always positive; use type field for direction
- If you cannot read a value clearly, use null
- Do not invent or infer transactions not present in the document
- Return [] if no transactions are found
"""

IMAGE_EXTRACTION_PROMPT = """
You are a receipt and bank notification parser. Extract the transaction details
from this image. Return ONLY a valid JSON object — no preamble, no markdown.

Schema:
{
  "date": "YYYY-MM-DD or null",
  "merchant": "merchant name or null",
  "amount": 1234.56,
  "type": "credit" | "debit",
  "currency": "NGN",
  "category_hint": "food|transport|utilities|shopping|health|entertainment|other"
}
"""


class ExtractedTransaction(BaseModel):
    date: str | None
    description: str | None
    amount: float
    type: Literal["credit", "debit"]
    balance_after: float | None = None
    reference: str | None = None


class ExtractedReceiptItem(BaseModel):
    date: str | None
    merchant: str | None
    amount: float
    type: Literal["credit", "debit"]
    currency: str = "NGN"
    category_hint: str | None = None


async def extract_from_pdf(pdf_text: str) -> list[ExtractedTransaction]:
    """
    Send extracted PDF text to Claude Sonnet for transaction parsing.
    Returns validated list of transactions.
    Raises ValueError with raw output on parse failure for debugging.
    """
    response = await client_anthropic.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": f"{PDF_EXTRACTION_PROMPT}\n\n---\n\n{pdf_text}"
        }]
    )

    raw = response.content[0].text.strip()

    try:
        data = json.loads(raw)
        return [ExtractedTransaction(**item) for item in data]
    except (json.JSONDecodeError, ValidationError) as e:
        raise ValueError(f"LLM returned invalid extraction format: {e}\nRaw output: {raw[:500]}")


async def extract_from_image(image_base64: str, media_type: str) -> ExtractedReceiptItem:
    """
    Send receipt/screenshot image to GPT-4o mini Vision for extraction.
    Raises ValueError with raw output on parse failure.
    """
    response = await client_openai.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{media_type};base64,{image_base64}",
                        "detail": "high"
                    }
                },
                {"type": "text", "text": IMAGE_EXTRACTION_PROMPT}
            ]
        }]
    )

    raw = response.choices[0].message.content.strip()

    try:
        data = json.loads(raw)
        return ExtractedReceiptItem(**data)
    except (json.JSONDecodeError, ValidationError) as e:
        raise ValueError(f"Vision LLM returned invalid format: {e}\nRaw output: {raw[:500]}")
