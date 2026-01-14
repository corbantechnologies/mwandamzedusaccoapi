import resend
import logging
from datetime import datetime
from django.template.loader import render_to_string
from mwandamzeduapi.settings import DOMAIN

logger = logging.getLogger(__name__)

current_year = datetime.now().year


def notify_guarantor_on_request(guarantee_request, site_url=DOMAIN):
    """
    1. Notifying guarantor on request submission
    """
    try:
        guarantor_user = guarantee_request.guarantor.member
        member = guarantee_request.member

        context = {
            "guarantor": guarantor_user,
            "requestor_name": f"{member.first_name} {member.last_name}",
            "amount": guarantee_request.guaranteed_amount,
            "reference": guarantee_request.reference,
            "current_year": current_year,
            "site_url": site_url,
        }

        email_body = render_to_string("new_guarantee_request.html", context)

        params = {
            "from": "Mwanda Mzedu SACCO <loans@wananchimali.com>",
            "to": [guarantor_user.email],
            "subject": f"New Guarantee Request from {member.first_name}",
            "html": email_body,
        }

        email = resend.Emails.send(params)
        logger.info(f"Guarantee request email sent to {guarantor_user.email}: {email}")

    except Exception as e:
        logger.error(f"Failed to send guarantee request email: {str(e)}")


def notify_guarantor_on_status_change(guarantee_request):
    """
    2. Notifying guarantor on request status changes
    """
    try:
        guarantor_user = guarantee_request.guarantor.member
        member = guarantee_request.member

        context = {
            "guarantor": guarantor_user,
            "requestor_name": f"{member.first_name} {member.last_name}",
            "status": guarantee_request.status,
            "amount": guarantee_request.guaranteed_amount,
            "current_year": current_year,
        }

        email_body = render_to_string("guarantee_request_status_change.html", context)

        params = {
            "from": "Mwanda Mzedu SACCO <loans@wananchimali.com>",
            "to": [guarantor_user.email],
            "subject": f"Guarantee Request {guarantee_request.status}",
            "html": email_body,
        }

        email = resend.Emails.send(params)
        logger.info(
            f"Guarantee status email sent to guarantor {guarantor_user.email}: {email}"
        )

    except Exception as e:
        logger.error(f"Failed to send guarantee status email to guarantor: {str(e)}")


def notify_member_on_guarantee_response(guarantee_request):
    """
    3. Notifying member on request status changes
    """
    try:
        member = guarantee_request.member
        guarantor_user = guarantee_request.guarantor.member

        context = {
            "member": member,
            "guarantor_name": f"{guarantor_user.first_name} {guarantor_user.last_name}",
            "status": guarantee_request.status,
            "amount": guarantee_request.guaranteed_amount,
            "current_year": current_year,
        }

        email_body = render_to_string("guarantee_response_for_member.html", context)

        params = {
            "from": "Mwanda Mzedu SACCO <loans@wananchimali.com>",
            "to": [member.email],
            "subject": f"Guarantee Request {guarantee_request.status}",
            "html": email_body,
        }

        email = resend.Emails.send(params)
        logger.info(f"Guarantee response email sent to member {member.email}: {email}")

    except Exception as e:
        logger.error(f"Failed to send guarantee response email to member: {str(e)}")
