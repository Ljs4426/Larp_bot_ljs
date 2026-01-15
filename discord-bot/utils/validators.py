"""Input validation utilities for Discord bot."""

import re
from datetime import datetime
from typing import Optional, Tuple
import discord


class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass


def validate_funds_needed(amount: int) -> bool:
    """
    Validate the funds needed amount.
    
    Args:
        amount: The amount to validate
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If amount is invalid
    """
    if not isinstance(amount, int):
        raise ValidationError("Funds needed must be an integer.")
    
    if amount < 1:
        raise ValidationError("Funds needed must be at least 1.")
    
    if amount > 999999999:
        raise ValidationError("Funds needed cannot exceed 999,999,999.")
    
    return True


def validate_url(url: str) -> bool:
    """
    Validate URL format and ensure it's HTTPS.
    
    Args:
        url: The URL to validate
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If URL is invalid
    """
    if not isinstance(url, str):
        raise ValidationError("URL must be a string.")
    
    # Sanitize input
    url = url.strip()
    
    # Check for https only
    if not url.startswith('https://'):
        raise ValidationError("URL must use HTTPS protocol.")
    
    # Basic URL validation regex
    url_pattern = re.compile(
        r'^https://'  # https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE
    )
    
    if not url_pattern.match(url):
        raise ValidationError("Invalid URL format.")
    
    return True


def validate_image_attachment(attachment: discord.Attachment) -> bool:
    """
    Validate image attachment type and size.
    
    Args:
        attachment: Discord attachment to validate
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If attachment is invalid
    """
    # Check file size (10MB limit)
    max_size = 10 * 1024 * 1024  # 10MB in bytes
    if attachment.size > max_size:
        raise ValidationError(f"File size must not exceed 10MB. Your file is {attachment.size / (1024*1024):.2f}MB.")
    
    # Check file extension
    allowed_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
    file_ext = attachment.filename.lower()
    
    if not any(file_ext.endswith(ext) for ext in allowed_extensions):
        raise ValidationError(f"File must be an image (PNG, JPG, JPEG, GIF, or WebP). Got: {attachment.filename}")
    
    # Check content type
    if attachment.content_type and not attachment.content_type.startswith('image/'):
        raise ValidationError("File must be an image type.")
    
    return True


def validate_date_string(date_str: str) -> Tuple[datetime, str]:
    """
    Validate and parse date string.
    
    Args:
        date_str: Date string in MM/DD/YYYY or YYYY-MM-DD format
        
    Returns:
        Tuple of (parsed datetime object, error message if any)
        
    Raises:
        ValidationError: If date format is invalid
    """
    if not isinstance(date_str, str):
        raise ValidationError("Date must be a string.")
    
    date_str = date_str.strip()
    
    # Try MM/DD/YYYY format
    try:
        parsed_date = datetime.strptime(date_str, '%m/%d/%Y')
        return parsed_date, None
    except ValueError:
        pass
    
    # Try YYYY-MM-DD format
    try:
        parsed_date = datetime.strptime(date_str, '%Y-%m-%d')
        return parsed_date, None
    except ValueError:
        pass
    
    raise ValidationError("Invalid date format. Please use MM/DD/YYYY or YYYY-MM-DD.")


def validate_reason_length(reason: str, max_length: int = 1024) -> bool:
    """
    Validate reason text length.
    
    Args:
        reason: The reason text to validate
        max_length: Maximum allowed length (default 1024 for embed fields)
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If reason is too long or empty
    """
    if not isinstance(reason, str):
        raise ValidationError("Reason must be text.")
    
    reason = reason.strip()
    
    if not reason:
        raise ValidationError("Reason cannot be empty.")
    
    if len(reason) > max_length:
        raise ValidationError(f"Reason cannot exceed {max_length} characters. Current length: {len(reason)}")
    
    return True


def sanitize_text(text: str) -> str:
    """
    Sanitize text input to prevent injection attacks.
    
    Args:
        text: Text to sanitize
        
    Returns:
        Sanitized text
    """
    if not isinstance(text, str):
        return str(text)
    
    # Discord automatically escapes most things, but we'll be extra careful
    # Remove null bytes
    text = text.replace('\x00', '')
    
    # Limit length to prevent DOS
    if len(text) > 2000:
        text = text[:2000]
    
    return text.strip()


def validate_discord_id(snowflake: str) -> bool:
    """
    Validate Discord snowflake ID.
    
    Args:
        snowflake: Discord ID to validate
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If ID is invalid
    """
    if not isinstance(snowflake, (str, int)):
        raise ValidationError("Discord ID must be a string or integer.")
    
    try:
        snowflake_int = int(snowflake)
        # Discord snowflakes are 64-bit integers
        if snowflake_int < 0 or snowflake_int > 9223372036854775807:
            raise ValidationError("Invalid Discord ID format.")
        return True
    except ValueError:
        raise ValidationError("Discord ID must be numeric.")
