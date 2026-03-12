import re
from datetime import datetime
from typing import Tuple
import discord


class ValidationError(Exception):
    pass


def validate_funds_needed(amount: int) -> bool:
    if not isinstance(amount, int):
        raise ValidationError("Funds needed must be an integer.")
    if amount < 1:
        raise ValidationError("Funds needed must be at least 1.")
    if amount > 999999999:
        raise ValidationError("Funds needed cannot exceed 999,999,999.")
    return True


def validate_url(url: str) -> bool:
    if not isinstance(url, str):
        raise ValidationError("URL must be a string.")
    url = url.strip()
    if not url.startswith('https://'):
        raise ValidationError("URL must use HTTPS.")
    url_pattern = re.compile(
        r'^https://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$', re.IGNORECASE
    )
    if not url_pattern.match(url):
        raise ValidationError("Invalid URL format.")
    return True


def validate_image_attachment(attachment: discord.Attachment) -> bool:
    max_size = 10 * 1024 * 1024
    if attachment.size > max_size:
        raise ValidationError(
            f"File too large — max 10MB, yours is {attachment.size / (1024*1024):.2f}MB."
        )
    allowed = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
    if not any(attachment.filename.lower().endswith(ext) for ext in allowed):
        raise ValidationError(
            f"File must be an image (PNG, JPG, GIF, or WebP). Got: {attachment.filename}"
        )
    if attachment.content_type and not attachment.content_type.startswith('image/'):
        raise ValidationError("File content type doesn't look like an image.")
    return True


def validate_date_string(date_str: str) -> Tuple[datetime, None]:
    if not isinstance(date_str, str):
        raise ValidationError("Date must be a string.")
    date_str = date_str.strip()
    for fmt in ('%m/%d/%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(date_str, fmt), None
        except ValueError:
            pass
    raise ValidationError("Invalid date format. Use MM/DD/YYYY or YYYY-MM-DD.")


def validate_reason_length(reason: str, max_length: int = 1024) -> bool:
    if not isinstance(reason, str):
        raise ValidationError("Reason must be text.")
    reason = reason.strip()
    if not reason:
        raise ValidationError("Reason cannot be empty.")
    if len(reason) > max_length:
        raise ValidationError(f"Reason is too long ({len(reason)} chars, max {max_length}).")
    return True


def sanitize_text(text: str) -> str:
    if not isinstance(text, str):
        return str(text)
    text = text.replace('\x00', '')
    return text[:2000].strip()


def validate_discord_id(snowflake) -> bool:
    try:
        val = int(snowflake)
        if val < 0 or val > 9223372036854775807:
            raise ValidationError("Invalid Discord ID.")
        return True
    except (ValueError, TypeError):
        raise ValidationError("Discord ID must be numeric.")
