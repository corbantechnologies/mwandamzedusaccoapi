import logging

from savings.models import SavingsAccount
from savingtypes.models import SavingType
from venturetypes.models import VentureType
from ventureaccounts.models import VentureAccount
from guarantors.models import GuarantorProfile
from feetypes.models import FeeType
from feeaccounts.models import FeeAccount

logger = logging.getLogger(__name__)


def create_member_accounts(member):
    """
    Create accounts for a member
    """
    # Existing savings account creation
    savings_types = SavingType.objects.all()
    created_accounts = []
    for savings_type in savings_types:
        if not SavingsAccount.objects.filter(
            member=member, account_type=savings_type
        ).exists():
            account = SavingsAccount.objects.create(
                member=member, account_type=savings_type, is_active=True
            )
            created_accounts.append(str(account))
    logger.info(
        f"Created {len(created_accounts)} SavingsAccounts for {member.member_no}: {', '.join(created_accounts)}"
    )
    # Existing venture account creation
    venture_types = VentureType.objects.all()
    created_accounts = []
    for venture_type in venture_types:
        if not VentureAccount.objects.filter(
            member=member, venture_type=venture_type
        ).exists():
            account = VentureAccount.objects.create(
                member=member, venture_type=venture_type, is_active=True
            )
            created_accounts.append(str(account))
    logger.info(
        f"Created {len(created_accounts)} VentureAccounts for {member.member_no}: {', '.join(created_accounts)}"
    )
    # Existing fee account creation

    # Do we this need? Say maybe contribution started and a member was not active then, so no fee account was created for them
    fee_types = FeeType.objects.filter(is_everyone=True)
    created_accounts = []
    for fee_type in fee_types:
        if not FeeAccount.objects.filter(member=member, fee_type=fee_type).exists():
            account = FeeAccount.objects.create(
                member=member,
                fee_type=fee_type,
                outstanding_balance=fee_type.amount,
            )
            created_accounts.append(str(account))
    logger.info(
        f"Created {len(created_accounts)} FeeAccounts for {member.member_no}: {', '.join(created_accounts)}"
    )
