import string
import secrets
from datetime import datetime


def generate_payment_account_code():
    """Generate a random 10-digit account number."""
    year = datetime.now().year % 100
    random_number = "".join(secrets.choice(string.digits) for _ in range(6))
    return f"PM{year}{random_number}"
