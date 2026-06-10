"""
Утилиты для работы с сертификатами (переиспользуются разными модулями)
Вывод логов и разбор certutil для сценариев проверки/очистки сертификатов.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, datetime

from cryptography import x509
from cryptography.hazmat.primitives import hashes

type LogFunc = Callable[[str], None]

def log_lines(lines: str | None, log_func: LogFunc = print) -> None:
    """Выводит лог построчно, пропуская пустые строки."""
    if not lines:
        return
    for line in lines.splitlines():
        if line.strip():
            log_func(line.strip())


def normalize_fingerprint(value: str | None) -> str | None:
    """Нормализует отпечаток сертификата (убирает пробелы/двоеточия, приводит к нижнему
    регистру)."""
    if not value:
        return None
    return value.replace(":", "").replace(" ", "").strip().lower()


def parse_openssl_fingerprint(output: str | None) -> str | None:
    """Разбирает вывод отпечатка OpenSSL и возвращает нормализованный SHA1-отпечаток."""
    if not output:
        return None
    for line in output.splitlines():
        if "fingerprint=" in line.lower():
            return normalize_fingerprint(line.split("=", 1)[1])
    return None


def parse_openssl_enddate_to_unix(output: str | None) -> int | None:
    """Разбирает вывод OpenSSL notAfter и преобразует в Unix-время (секунды)."""
    if not output:
        return None
    for line in output.splitlines():
        lower = line.lower()
        if lower.startswith("notafter="):
            date_str = line.split("=", 1)[1].strip()
            if date_str.endswith(" GMT"):
                date_str = date_str[:-4].strip()
            normalized = " ".join(date_str.split())
            try:
                parsed = datetime.strptime(normalized, "%b %d %H:%M:%S %Y")
            except ValueError:
                return None
            return int(parsed.replace(tzinfo=UTC).timestamp())
    return None


def certificate_fingerprint_sha1(certificate: x509.Certificate) -> str:
    """Извлекает SHA1-отпечаток сертификата и нормализует его."""
    return normalize_fingerprint(certificate.fingerprint(hashes.SHA1()).hex()) or ""


def certificate_not_after_unix(certificate: x509.Certificate) -> int:
    """Преобразует срок действия сертификата в Unix-время (секунды)."""
    not_after_utc = getattr(certificate, "not_valid_after_utc", None)
    if isinstance(not_after_utc, datetime):
        return int(not_after_utc.timestamp())
    return int(certificate.not_valid_after.replace(tzinfo=UTC).timestamp())


def certificate_name_to_text(name: x509.Name) -> str:
    """Преобразует объект имени cryptography в читаемую строку."""
    return name.rfc4514_string()


def parse_certutil_store(output: str) -> list[dict[str, str]]:
    """Разбирает вывод certutil -store и извлекает subject/issuer/thumbprint."""
    entries: list[dict[str, str]] = []
    current: dict[str, str] = {}

    def flush() -> None:
        if current:
            entries.append(current.copy())
            current.clear()

    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        lower = line.lower()
        if lower.startswith("================"):
            flush()
            continue

        if lower.startswith(("使用者:", "subject:")):
            current["subject"] = line.split(":", 1)[1].strip()
            continue

        if lower.startswith(("颁发者:", "issuer:")):
            current["issuer"] = line.split(":", 1)[1].strip()
            continue

        if "证书哈希" in line or lower.startswith("certificate hash"):
            current["thumbprint"] = line.split(":", 1)[1].strip().replace(" ", "")
            continue

    flush()
    return entries


def filter_certs_by_name(
    entries: Iterable[dict[str, str]],
    ca_common_name: str,
) -> list[dict[str, str]]:
    """Фильтрует записи сертификатов по CA common name."""
    target = ca_common_name.lower()
    matched: list[dict[str, str]] = []
    for entry in entries:
        subject = entry.get("subject", "")
        issuer = entry.get("issuer", "")
        if target in subject.lower() or target in issuer.lower():
            matched.append(entry)
    return matched


__all__ = [
    "certificate_fingerprint_sha1",
    "certificate_name_to_text",
    "certificate_not_after_unix",
    "filter_certs_by_name",
    "log_lines",
    "normalize_fingerprint",
    "parse_certutil_store",
    "parse_openssl_enddate_to_unix",
    "parse_openssl_fingerprint",
]
