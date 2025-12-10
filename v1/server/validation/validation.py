import re
from datetime import datetime
from typing import Dict

def is_valid_username(username: str) -> bool:
    if not isinstance(username, str):
        return False
    return re.fullmatch(r"[A-Za-z_][A-Za-z0-9_'.]{7,9}", username) is not None

def is_valid_password(password: str) -> bool:
    if not isinstance(password, str):
        return False
    length_valid = 12 <= len(password) <= 30
    has_lowercase = re.search(r"[a-z]", password) is not None
    has_uppercase = re.search(r"[A-Z]", password) is not None
    has_digit = re.search(r"[0-9]", password) is not None
    has_special = re.search(r"[~!@#$%&_+\-=`|\\(){}\[\]:;'<>,.?/]", password) is not None
    return bool(length_valid and has_lowercase and has_uppercase and has_digit and has_special)

def is_valid_email(email: str) -> bool:
    if not isinstance(email, str):
        return False
    return re.fullmatch(r"[^@]+@[^@]+\.[^@]+", email) is not None

def is_valid_phone(phone: str) -> bool:
    """
    Validates phone numbers worldwide.
    Accepts: digits, spaces, dashes, parentheses, plus sign
    Length: 7-15 digits (covers most international formats)
    Examples: +1-555-123-4567, (555) 123-4567, +31612345678, 0612345678
    """
    if not isinstance(phone, str):
        return False
    # Remove common separators to count digits
    digits_only = re.sub(r'[\s\-\(\)\+]', '', phone)
    # Must have 7-15 digits and only contain valid phone characters
    if not re.fullmatch(r'[0-9]{7,15}', digits_only):
        return False
    # Original string should only contain digits and common separators
    return re.fullmatch(r'[\d\s\-\(\)\+]+', phone) is not None

def is_valid_license_plate(license_plate: str) -> bool:
    """
    Validates license plates worldwide.
    Accepts: letters, numbers, spaces, dashes
    Length: 2-15 characters (covers most international formats)
    Examples: ABC-123, 12-ABC-34, XX 1234 YY, 1ABC234
    """
    if not isinstance(license_plate, str):
        return False
    # Remove spaces and dashes for length check
    clean = re.sub(r'[\s\-]', '', license_plate)
    # Must have 2-15 alphanumeric characters
    if not (2 <= len(clean) <= 15):
        return False
    # Can only contain letters, numbers, spaces, and dashes
    return re.fullmatch(r'[A-Z0-9\s\-]+', license_plate.upper()) is not None

def is_valid_role(role: str) -> bool:
    if not isinstance(role, str):
        return False
    return role.upper() in {"USER", "ADMIN"}
