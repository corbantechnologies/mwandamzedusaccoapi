import threading
import json
from django.utils.deprecation import MiddlewareMixin
from auditlogs.models import AuditLog

class AuditLogMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request._body_data = request.body
        
    def process_response(self, request, response):
        if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            # Try to get the user
            user = request.user if hasattr(request, 'user') and request.user.is_authenticated else None
            
            # Module logic based on path
            path = request.path
            path_parts = [p for p in path.split('/') if p]
            module = path_parts[1] if len(path_parts) > 1 else 'general'
            
            # Action logic based on method and status
            action = f"{request.method}_{response.status_code}"
            if request.method == 'POST' and 'login' in path:
                action = 'LOGIN'
            
            # Extract IP
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0]
            else:
                ip_address = request.META.get('REMOTE_ADDR')

            # Descriptive text
            description = f"{request.method} request to {path}"
            if user:
                description += f" by {user.get_full_name()} ({user.member_no})"
            else:
                description += " by anonymous user"
            
            if response.status_code >= 400:
                description += f" failed with status {response.status_code}"
            else:
                description += f" succeeded with status {response.status_code}"
                
            # Attempt to extract contextual payload details
            request_payload = None
            response_payload = None
            payload_details = {}
            sensitive_keys = ['password', 'confirm_password', 'old_password', 'new_password', 'token', 'access', 'refresh', 'pin']
            
            try:
                # 1. Extract from request body
                if hasattr(request, '_body_data') and request._body_data:
                    data = json.loads(request._body_data.decode('utf-8'))
                    if isinstance(data, dict):
                        request_payload = {k: v for k, v in data.items() if k.lower() not in sensitive_keys}
                        for key, value in data.items():
                            if key.lower() not in sensitive_keys and isinstance(value, (str, int, float, bool)):
                                payload_details[key] = value

                # 2. Extract from response
                if response.status_code in [200, 201] and 'application/json' in response.get('Content-Type', ''):
                    resp_data = json.loads(response.content.decode('utf-8'))
                    if isinstance(resp_data, dict):
                        response_payload = {k: v for k, v in resp_data.items() if k.lower() not in sensitive_keys}
                        for k in ['reference', 'amount', 'status', 'member_no', 'id', 'name']:
                            if k in resp_data and k not in payload_details:
                                payload_details[k] = resp_data[k]
                    elif isinstance(resp_data, list):
                        response_payload = resp_data
            except Exception:
                pass
                
            if payload_details:
                details_str = ", ".join([f"{k}: {v}" for k, v in payload_details.items()])
                description += f". Context Details: {details_str}"
                
            def _create_log():
                AuditLog.objects.create(
                    user=user,
                    action=action,
                    module=module,
                    description=description,
                    ip_address=ip_address,
                    request_payload=request_payload,
                    response_payload=response_payload
                )
                
            thread = threading.Thread(target=_create_log)
            thread.start()
            
        return response
