"""Hash de contraseñas (Argon2) y generación de tokens."""

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()
# Hash ficticio para que verificar un correo inexistente tarde lo mismo que uno real.
_HASH_FICTICIO = _hasher.hash("contraseña-ficticia-para-igualar-tiempos")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verificar_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _HASH_FICTICIO, password) and bool(password_hash)
    except (VerificationError, InvalidHashError):
        return False


def nuevo_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
