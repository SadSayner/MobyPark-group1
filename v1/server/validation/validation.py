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
    if not isinstance(phone, str):
        return False
    return re.fullmatch(r"\+?[1-9]\d{1,14}", phone) is not None

def is_valid_role(role: str) -> bool:
    if not isinstance(role, str):
        return False
    return role.upper() in {"USER", "ADMIN"}
