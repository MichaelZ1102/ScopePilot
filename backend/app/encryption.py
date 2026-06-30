"""Token/secret encryption helpers using Fernet symmetric encryption.

Encryption key is derived from the app's SECRET_KEY so no additional
environment variable is needed per deployment.
"""
import base64
import hashlib

from cryptography.fernet import Fernet

from .config import settings

# Derive a 32-byte Fernet key from the app's secret_key
_KEY = base64.urlsafe_b64encode(
    hashlib.sha256(settings.secret_key.encode()).digest()
)
_fernet = Fernet(_KEY)


def encrypt(plaintext: str) -> str:
    """Encrypt a plaintext string (e.g. API token) into a Fernet token."""
    if not plaintext:
        return ""
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt a Fernet token back to plaintext string."""
    if not ciphertext:
        return ""
    return _fernet.decrypt(ciphertext.encode()).decode()
