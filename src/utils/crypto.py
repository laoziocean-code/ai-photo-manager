"""API Key 本地加密（Fernet）。

设计要点：
- 密钥由「机器指纹（MAC + 固定盐）」派生，存于本机配置，不联网、不上传。
- 换机器无法直接解密（即安全设计）。
- 注：此为本地混淆级保护，非绝对安全；用户自行承担 API 密钥安全责任。
"""
import base64
import hashlib
import uuid

from cryptography.fernet import Fernet

_SALT = b"ai-photography-manager-v1"


def _derive_key() -> bytes:
    node = uuid.getnode()
    material = f"{node}-{uuid.uuid3(uuid.NAMESPACE_DNS, 'ai-photo')}".encode("utf-8")
    digest = hashlib.pbkdf2_hmac("sha256", material, _SALT, 100_000)
    return base64.urlsafe_b64encode(digest[:32])


def encrypt_string(plain: str) -> str:
    return Fernet(_derive_key()).encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt_string(token: str) -> str:
    return Fernet(_derive_key()).decrypt(token.encode("utf-8")).decode("utf-8")
