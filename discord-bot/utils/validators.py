import re
from datetime import datetime
from typing import Optional, Tuple
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
        raise ValidationError("URL must use HTTPS protocol.")

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
    max_size = 10 * 1024 * 1024  # 10MB
    if attachment.size > max_size:
        raise ValidationError(f"File size must not exceed 10MB. Your file is {attachment.size / (1024*1024):.2f}MB.")

    allowed_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
    file_ext = attachment.filename.lower()

    if not any(file_ext.endswith(ext) for ext in allowed_extensions):
        raise ValidationError(f"File must be an image (PNG, JPG, JPEG, GIF, or WebP). Got: {attachment.filename}")

    if attachment.content_type and not attachment.content_type.startswith('image/'):
        raise ValidationError("File must be an image type.")
    return True


def validate_date_string(date_str: str) -> Tuple[datetime, str]:
    if not isinstance(date_str, str):
        raise ValidationError("Date must be a string.")

    date_str = date_str.strip()

    try:
        parsed_date = datetime.strptime(date_str, '%m/%d/%Y')
        return parsed_date, None
    except ValueError:
        pass

    try:
        parsed_date = datetime.strptime(date_str, '%Y-%m-%d')
        return parsed_date, None
    except ValueError:
        pass

    raise ValidationError("Invalid date format. Please use MM/DD/YYYY or YYYY-MM-DD.")


def validate_reason_length(reason: str, max_length: int = 1024) -> bool:
    if not isinstance(reason, str):
        raise ValidationError("Reason must be text.")

    reason = reason.strip()

    if not reason:
        raise ValidationError("Reason cannot be empty.")

    if len(reason) > max_length:
        raise ValidationError(f"Reason cannot exceed {max_length} characters. Current length: {len(reason)}")
    return True


def sanitize_text(text: str) -> str:
    if not isinstance(text, str):
        return str(text)

    text = text.replace('\x00', '')

    if len(text) > 2000:
        text = text[:2000]
    return text.strip()


def validate_discord_id(snowflake: str) -> bool:
    if not isinstance(snowflake, (str, int)):
        raise ValidationError("Discord ID must be a string or integer.")

    try:
        snowflake_int = int(snowflake)
        if snowflake_int < 0 or snowflake_int > 9223372036854775807:
            raise ValidationError("Invalid Discord ID format.")
        return True
    except ValueError:
        raise ValidationError("Discord ID must be numeric.")
