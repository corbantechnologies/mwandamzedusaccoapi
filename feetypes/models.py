from django.db import models

from accounts.abstracts import TimeStampedModel, UniversalIdModel, ReferenceModel
from glaccounts.models import GLAccount


class FeeType(UniversalIdModel, TimeStampedModel, ReferenceModel):
    """
    - Created by sacco admin
    - Handles fees like membership fee, loan fee, share capital, penalties, contributions etc
    - Can be applied to everyone or specific members: if for everyone, fee accounts will be created automatically
    - If for specific members, fee accounts will be created for each member
    - Do we need to specify the members? if yes, what is there are 1000+ members?
        - Will the admin go one by one and create the Fee Account for each member?
        - Or will the admin select a group of members then a trigger will create the Fee Account for each member?
    - GL account is required
    """

    name = models.CharField(max_length=255, unique=True)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    is_everyone = models.BooleanField(default=False, help_text="Apply to everyone")
    can_exceed_limit = models.BooleanField(default=False, help_text="Can exceed limit")
    gl_account = models.ForeignKey(
        GLAccount, on_delete=models.PROTECT, related_name="fee_types"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Fee Type"
        verbose_name_plural = "Fee Types"
        ordering = ["-created_at"]
