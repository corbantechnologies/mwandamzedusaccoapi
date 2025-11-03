from abc import ABC, abstractmethod


class GuaranteeRule(ABC):
    @abstractmethod
    def validate(self, application, requests):
        pass


class Coverage100Rule(GuaranteeRule):
    def validate(self, application, requests):
        total = sum(r.guaranteed_amount for r in requests if r.status == "Accepted")
        if total < application.requested_amount:
            return False, f"Coverage: {total}/{application.requested_amount}"
        return True, ""


class MaxGuaranteesRule(GuaranteeRule):
    def validate(self, application, requests):
        for req in requests:
            if (
                req.guarantor.active_guarantees_count()
                >= req.guarantor.max_active_guarantees
            ):
                return False, f"{req.guarantor} has reached limit"
        return True, ""


GUARANTEE_RULES = [Coverage100Rule(), MaxGuaranteesRule()]


def validate_guarantee_rules(application):
    from loanapplications.models import GuaranteeRequest

    accepted = application.guarantee_requests.filter(status="Accepted")
    for rule in GUARANTEE_RULES:
        ok, msg = rule.validate(application, accepted)
        if not ok:
            return False, msg
    return True, "Ready to submit"
