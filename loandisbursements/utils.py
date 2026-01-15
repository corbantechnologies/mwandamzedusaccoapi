import string
import random
from datetime import datetime

current_year = datetime.now().year


def generate_loan_disbursement_code(length=12):
    characters = string.digits
    year = str(current_year)[2:]
    return (
        f"MMS{year}" + "".join(random.choice(characters) for _ in range(length)) + "LD"
    )
