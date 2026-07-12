import threading

def log_action(user, action, module, description, ip_address=None):
    from auditlogs.models import AuditLog
    
    def _create_log():
        AuditLog.objects.create(
            user=user,
            action=action,
            module=module,
            description=description,
            ip_address=ip_address
        )
        
    thread = threading.Thread(target=_create_log)
    thread.start()
