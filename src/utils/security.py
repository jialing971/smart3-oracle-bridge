"""管理员密码工具（SHA-256，不依赖第三方库）

默认密码：admin
对应哈希：8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918
"""
import hashlib


def hash_password(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def verify_password(plaintext: str, stored_hash: str) -> bool:
    return hash_password(plaintext) == stored_hash
