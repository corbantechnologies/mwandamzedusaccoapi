import string
import secrets
from datetime import datetime


def generate_penalty_code():
    """Generate a random 10-digit penalty code."""
    year = datetime.now().year % 100
    random_number = "".join(secrets.choice(string.digits) for _ in range(8))
    return f"PC{year}{random_number}"
