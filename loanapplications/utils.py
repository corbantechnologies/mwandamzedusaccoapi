import resend

from decimal import Decimal
from django.db import models
from savings.models import SavingsAccount
from loanapplications.models import LoanApplication


def compute_loan_coverage(application):
    """
    Returns accurate coverage using:
    - Available self-guarantee (savings - committed from active loans)
    - Accepted external guarantees
    """
    total_savings = SavingsAccount.objects.filter(member=application.member).aggregate(
        t=models.Sum("balance")
    )["t"] or Decimal("0")

    # Calculate available based on GuarantorProfile logic
    try:
        from guarantors.models import GuarantorProfile

        profile = GuarantorProfile.objects.get(member=application.member)
        # Sync max_guarantee just in case (optional, but good for accuracy)
        # profile.max_guarantee_amount = total_savings
        # profile.save()

        # Committed includes guarantees for others AND self-guarantees on other loans
        committed_total = profile.committed_guarantee_amount
    except GuarantorProfile.DoesNotExist:
        committed_total = Decimal("0")

    available_self = max(Decimal("0"), total_savings - committed_total)

    total_guaranteed_by_others = application.guarantors.filter(
        status="Accepted"
    ).aggregate(t=models.Sum("guaranteed_amount"))["t"] or Decimal("0")

    effective_coverage = available_self + total_guaranteed_by_others
    remaining_to_cover = max(
        Decimal("0"), application.requested_amount - effective_coverage
    )
    is_fully_covered = remaining_to_cover <= 0

    return {
        "total_savings": total_savings,
        "committed_self_guarantee": committed_total,
        "available_self_guarantee": available_self,
        "total_guaranteed_by_others": total_guaranteed_by_others,
        "effective_coverage": effective_coverage,
        "remaining_to_cover": remaining_to_cover,
        "is_fully_covered": is_fully_covered,
    }


import logging
from datetime import datetime
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)
current_year = datetime.now().year


def notify_member_on_loan_submission(loan_application):
    """
    1. Notifying member on loan submissions
    """
    try:
        member = loan_application.member
        context = {
            "member": member,
            "product_name": loan_application.product.name,
            "amount": loan_application.requested_amount,
            "reference": loan_application.reference,
            "current_year": current_year,
        }

        email_body = render_to_string("loan_submitted.html", context)

        params = {
            "from": "Mwanda Mzedu SACCO <loans@wananchimali.com>",
            "to": [member.email],
            "subject": "Loan Application Submitted",
            "html": email_body,
        }

        email = resend.Emails.send(params)
        logger.info(f"Loan submission email sent to {member.email}: {email}")

    except Exception as e:
        logger.error(f"Failed to send loan submission email: {str(e)}")


def notify_member_on_loan_status_change(loan_application):
    """
    2. Notifying members on loan status changes
    """
    try:
        member = loan_application.member
        context = {
            "member": member,
            "product_name": loan_application.product.name,
            "amount": loan_application.requested_amount,
            "status": loan_application.status,
            "current_year": current_year,
        }

        email_body = render_to_string("loan_status_change.html", context)

        params = {
            "from": "Mwanda Mzedu SACCO <loans@wananchimali.com>",
            "to": [member.email],
            "subject": f"Loan Application {loan_application.status}",
            "html": email_body,
        }

        email = resend.Emails.send(params)
        logger.info(f"Loan status email sent to {member.email}: {email}")

    except Exception as e:
        logger.error(f"Failed to send loan status email: {str(e)}")


def send_loan_application_approved_email(loan_application, loan_account):
    """
    3. Notifying members on loan application approval
    """
    try:
        member = loan_application.member
        context = {
            "member": member,
            "product_name": loan_application.product.name,
            "amount": loan_application.requested_amount,
            "loan_account_number": loan_account.account_number,
            "current_year": current_year,
        }

        email_body = render_to_string("loan_application_approved.html", context)

        params = {
            "from": "Mwanda Mzedu SACCO <loans@wananchimali.com>",
            "to": [member.email],
            "subject": "Loan Application Approved",
            "html": email_body,
        }

        email = resend.Emails.send(params)
        logger.info(f"Loan application approval email sent to {member.email}: {email}")

    except Exception as e:
        logger.error(f"Failed to send loan application approval email: {str(e)}")
