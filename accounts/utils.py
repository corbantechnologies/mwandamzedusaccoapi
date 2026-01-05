import string
import secrets
import resend
import logging
from datetime import datetime
from django.template.loader import render_to_string

from mwandamzeduapi.settings import DOMAIN

logger = logging.getLogger(__name__)


current_year = datetime.now().year


def generate_reference():
    characters = string.ascii_letters + string.digits
    random_string = "".join(secrets.choice(characters) for _ in range(12))
    return random_string.upper()


def generate_member_number():
    year = datetime.now().year % 100
    random_number = "".join(secrets.choice(string.digits) for _ in range(6))
    return f"M{year}{random_number}"


def send_account_created_by_admin_email(user, activation_link=None):
    email_body = render_to_string(
        "account_activation_email.html",
        {
            "user": user,
            "activation_link": activation_link,
            "current_year": datetime.now().year,
        },
    )
    params = {
        "from": "SACCO <onboarding@corbantechnologies.org>",
        "to": [user.email],
        "subject": "Activate Your Mwanda Mzedu SACCO Account",
        "html": email_body,
    }
    try:
        response = resend.Emails.send(params)
        logger.info(f"Email sent to {user.email} with response: {response}")
        return response
    except Exception as e:
        logger.error(f"Error sending email to {user.email}: {str(e)}")
        return None


def send_account_activated_email(user):
    """
    A function to send a successful account creation email
    """
    email_body = ""
    current_year = datetime.now().year

    try:

        email_body = render_to_string(
            "account_activated.html", {"user": user, "current_year": current_year}
        )
        params = {
            "from": "SACCO <onboarding@corbantechnologies.org>",
            "to": [user.email],
            "subject": "Welcome to Mwanda Mzedu SACCO",
            "html": email_body,
        }
        response = resend.Emails.send(params)
        logger.info(f"Email sent to {user.email} with response: {response}")
        return response

    except Exception as e:
        logger.error(f"Error sending email to {user.email}: {str(e)}")
        return None


def send_forgot_password_email(user, code):
    """
    A function to send a forgot password email
    """
    try:
        email_body = render_to_string(
            "forgot_password.html",
            {
                "user": user,
                "code": code,
                "current_year": datetime.now().year,
            },
        )
        params = {
            "from": "SACCO <security@corbantechnologies.org>",
            "to": [user.email],
            "subject": "Reset Your Mwanda Mzedu SACCO Password",
            "html": email_body,
        }
        response = resend.Emails.send(params)
        logger.info(f"Forgot password email sent to {user.email} with response: {response}")
        return response
    except Exception as e:
        logger.error(f"Error sending forgot password email to {user.email}: {str(e)}")
        return None


def send_password_reset_success_email(user):
    """
    A function to send a password reset success email
    """
    try:
        email_body = render_to_string(
            "password_reset_success.html",
            {
                "user": user,
                "current_year": datetime.now().year,
            },
        )
        params = {
            "from": "SACCO <security@corbantechnologies.org>",
            "to": [user.email],
            "subject": "Password Reset Successful - Mwanda Mzedu SACCO",
            "html": email_body,
        }
        response = resend.Emails.send(params)
        logger.info(f"Password reset success email sent to {user.email} with response: {response}")
        return response
    except Exception as e:
        logger.error(f"Error sending password reset success email to {user.email}: {str(e)}")
        return None