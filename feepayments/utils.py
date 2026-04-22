import resend
import logging
from datetime import datetime
import string
import secrets
import random
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)

current_year = datetime.now().year


def generate_fee_payment_code():
    """Generate a random 10-digit account number."""
    year = datetime.now().year % 100
    random_number = "".join(secrets.choice(string.digits) for _ in range(8))
    return f"FP{year}{random_number}"


def send_fee_payment_made_email(user, fee_payment):
    try:
        email_body = render_to_string(
            "fee_payment_made.html",
            {"user": user, "fee_payment": fee_payment, "current_year": current_year},
        )
        params = {
            "from": "SACCO <finance@wananchimali.com>",
            "to": [user.email],
            "subject": "Fee Payment Confirmation",
            "html": email_body,
        }
        response = resend.Emails.send(params)
        logger.info(f"Email sent to {user.email} with response: {response}")
        return response
    except Exception as e:
        logger.error(f"Error sending email to {user.email}: {str(e)}")
        return None
