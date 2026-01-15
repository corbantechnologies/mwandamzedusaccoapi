from django.apps import AppConfig


class LoanpaymentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "loanpayments"

    def ready(self):
        import loanpayments.signals
