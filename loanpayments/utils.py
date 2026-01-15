import string
import random
import resend
import logging
from datetime import datetime
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)

current_year = datetime.now().year


def generate_loan_payment_code(length=12):
    characters = string.digits
    year = str(current_year)[2:]
    return (
        f"MMS{year}" + "".join(random.choice(characters) for _ in range(length)) + "LP"
    )


def send_loan_payment_made_email(user, loan_payment):
    try:
        email_body = render_to_string(
            "loan_payment_made.html",
            {"user": user, "loan_payment": loan_payment, "current_year": current_year},
        )
        params = {
            "from": "Mwanda Mzedu SACCO <finance@wananchimali.com>",
            "to": [user.email],
            "subject": "You've made a loan payment!",
            "html": email_body,
        }
        response = resend.Emails.send(params)
        logger.info(f"Email sent to {user.email} with response: {response}")
        return response
    except Exception as e:
        logger.error(f"Error sending email to {user.email}: {str(e)}")
        return None
