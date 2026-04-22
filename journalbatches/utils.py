import string
import secrets
from datetime import datetime


def generate_journal_batch_code():
    """Generate a random 10-digit journal batch code."""
    year = datetime.now().year % 100
    random_number = "".join(secrets.choice(string.digits) for _ in range(8))
    return f"JB{year}{random_number}"
