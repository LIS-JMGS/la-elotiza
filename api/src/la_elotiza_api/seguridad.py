"""Hash de PIN y tokens de sesión (solo biblioteca estándar)."""

import hashlib
import hmac
import secrets

_ALGORITMO = "pbkdf2_sha256"
_ITERACIONES = 200_000


def hash_pin(pin: str) -> str:
    sal = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", pin.encode(), bytes.fromhex(sal), _ITERACIONES
    )
    return f"{_ALGORITMO}${_ITERACIONES}${sal}${digest.hex()}"


def verificar_pin(pin: str, guardado: str) -> bool:
    try:
        algoritmo, iteraciones, sal, esperado = guardado.split("$")
    except ValueError:
        return False
    if algoritmo != _ALGORITMO:
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256", pin.encode(), bytes.fromhex(sal), int(iteraciones)
    )
    return hmac.compare_digest(digest.hex(), esperado)


def nuevo_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Solo se guarda el hash: una copia de la base no da sesiones válidas."""
    return hashlib.sha256(token.encode()).hexdigest()
