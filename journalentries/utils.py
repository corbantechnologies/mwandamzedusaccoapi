import string
import secrets
from datetime import datetime


def generate_journal_entry_code():
    """Generate a random 10-digit journal entry code."""
    year = datetime.now().year % 100
    random_number = "".join(secrets.choice(string.digits) for _ in range(8))
    return f"JE{year}{random_number}"
