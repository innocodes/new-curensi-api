import uuid
import boto3
from botocore.exceptions import ClientError
from app.core.config import settings

FILE_RETENTION_DAYS = 14  # NDPR compliance — raw files deleted after 14 days

# Lazy — created on first use so an empty R2_ACCOUNT_ID doesn't crash at import time
_r2_client = None


def _get_r2_client():
    global _r2_client
    if _r2_client is None:
        if not settings.R2_ACCOUNT_ID:
            raise RuntimeError(
                "R2_ACCOUNT_ID is not configured. Set R2 credentials to use file storage."
            )
        _r2_client = boto3.client(
            "s3",
            endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            region_name="auto",
        )
    return _r2_client


def generate_r2_key(user_id: str, source: str, filename: str) -> str:
    """Format: {user_id}/{source}/{uuid}/{filename}"""
    return f"{user_id}/{source}/{uuid.uuid4()}/{filename}"


async def upload_to_r2(file_bytes: bytes, key: str, content_type: str) -> str:
    """Upload file bytes to R2. Returns the key."""
    _get_r2_client().put_object(
        Bucket=settings.R2_BUCKET_NAME,
        Key=key,
        Body=file_bytes,
        ContentType=content_type,
    )
    return key


async def fetch_from_r2(key: str) -> bytes:
    """Fetch file bytes from R2 by key."""
    response = _get_r2_client().get_object(Bucket=settings.R2_BUCKET_NAME, Key=key)
    return response["Body"].read()


async def delete_from_r2(key: str) -> None:
    """Delete a file from R2. Silently ignores 404s."""
    try:
        _get_r2_client().delete_object(Bucket=settings.R2_BUCKET_NAME, Key=key)
    except ClientError as e:
        if e.response["Error"]["Code"] != "NoSuchKey":
            raise


def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract plain text from PDF bytes using pypdf."""
    import io
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    return "\n\n".join(pages)
