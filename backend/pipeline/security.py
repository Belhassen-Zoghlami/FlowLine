import hashlib
import hmac
from cryptography.fernet import Fernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

def _fernet():
    key = settings.TOKEN_ENCRYPTION_KEY
    if not key:
        raise ImproperlyConfigured("TOKEN_ENCRYPTION_KEY is not")
    return Fernet(key.encode())

def encrypt(value):
    if not value:
        return ""
    return _fernet().encrypt(value.encode()).decode()

def decrypt(value):
    if not value:
        return ""
    return _fernet().decrypt(value.encode()).decode()

def webhook_signature(secret,body):
    if isinstance(body,str):
        body=body.encode()
    digest=hmac.new(secret.encode(),body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"

def verify_webhook_signature(secret,body, signature_header):
    if not secret or not signature_header:
        return False
    if isinstance(body,str):
        body=body.encode()
    return hmac.compare_digest(webhook_signature(secret,body), signature_header)