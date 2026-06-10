from __future__ import annotations

import ctypes
import shlex
from collections.abc import Callable
from ctypes import wintypes
from functools import lru_cache
from typing import Any, cast

from cryptography import x509

from modules.cert.cert_utils import (
    certificate_fingerprint_sha1,
    certificate_name_to_text,
    certificate_not_after_unix,
    filter_certs_by_name,
    log_lines,
    normalize_fingerprint,
    parse_certutil_store,
)
from modules.platform.macos_privileged_helper import get_mac_privileged_session
from modules.platform.system import is_macos, is_posix, is_windows
from modules.runtime.operation_result import OperationResult
from modules.runtime.process_utils import run_command

MAC_KEYCHAIN_ITEM_NOT_FOUND = 44

X509_ASN_ENCODING = 0x00000001
PKCS_7_ASN_ENCODING = 0x00010000
CERT_SYSTEM_STORE_LOCAL_MACHINE = 0x00020000
CERT_STORE_READONLY_FLAG = 0x00008000
CERT_FIND_SUBJECT_STR_W = 0x00080007
CERT_NAME_SIMPLE_DISPLAY_TYPE = 4
CERT_NAME_ISSUER_FLAG = 0x00000001
CERT_SHA1_HASH_PROP_ID = 3
MULTI_MATCH_THRESHOLD = 2
SYSTEM_STORE_PROVIDER = b"System"
SYSTEM_STORE_ROOT = "ROOT"
type LogFunc = Callable[[str], None]


class CRYPT_DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


class CRYPT_OBJID_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


class CRYPT_ALGORITHM_IDENTIFIER(ctypes.Structure):
    _fields_ = [
        ("pszObjId", wintypes.LPSTR),
        ("Parameters", CRYPT_OBJID_BLOB),
    ]


class CERT_NAME_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


class CERT_INFO(ctypes.Structure):
    _fields_ = [
        ("dwVersion", wintypes.DWORD),
        ("SerialNumber", CRYPT_DATA_BLOB),
        ("SignatureAlgorithm", CRYPT_ALGORITHM_IDENTIFIER),
        ("Issuer", CERT_NAME_BLOB),
        ("NotBefore", wintypes.FILETIME),
        ("NotAfter", wintypes.FILETIME),
    ]


class CERT_CONTEXT(ctypes.Structure):
    _fields_ = [
        ("dwCertEncodingType", wintypes.DWORD),
        ("pbCertEncoded", ctypes.POINTER(ctypes.c_byte)),
        ("cbCertEncoded", wintypes.DWORD),
        ("pCertInfo", ctypes.POINTER(CERT_INFO)),
        ("hCertStore", wintypes.HANDLE),
    ]


PCCERT_CONTEXT = ctypes.POINTER(CERT_CONTEXT)



def _split_pem_blocks(pem_text: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []
    in_block = False
    for line in pem_text.splitlines():
        if "BEGIN CERTIFICATE" in line:
            in_block = True
            current = [line]
            continue
        if "END CERTIFICATE" in line and in_block:
            current.append(line)
            blocks.append("\n".join(current) + "\n")
            in_block = False
            continue
        if in_block:
            current.append(line)
    return blocks


def _parse_pem_certificate(pem_block: str, log_func: LogFunc = print) -> dict[str, object] | None:
    try:
        certificate = x509.load_pem_x509_certificate(pem_block.encode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        log_func(f"⚠️ Не удалось разобрать PEM-сертификат: {exc}")
        return None

    return {
        "subject": certificate_name_to_text(certificate.subject),
        "issuer": certificate_name_to_text(certificate.issuer),
        "fingerprint_sha1": certificate_fingerprint_sha1(certificate),
        "not_after_unix": certificate_not_after_unix(certificate),
    }


def _filetime_to_unix(filetime: Any) -> int | None:
    if not filetime:
        return None
    value = (int(filetime.dwHighDateTime) << 32) + int(filetime.dwLowDateTime)
    if value <= 0:
        return None
    return int((value - 116444736000000000) // 10_000_000)


@lru_cache(maxsize=1)
def _get_crypt32():
    windll_factory = getattr(ctypes, "WinDLL", None)
    if windll_factory is None:
        raise RuntimeError("WinDLL is not available on this platform")
    crypt32 = windll_factory("crypt32", use_last_error=True)
    crypt32.CertOpenStore.argtypes = [
        wintypes.LPCSTR,
        wintypes.DWORD,
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPCWSTR,
    ]
    crypt32.CertOpenStore.restype = wintypes.HANDLE
    crypt32.CertCloseStore.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    crypt32.CertCloseStore.restype = wintypes.BOOL
    crypt32.CertFindCertificateInStore.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPCWSTR,
        PCCERT_CONTEXT,
    ]
    crypt32.CertFindCertificateInStore.restype = PCCERT_CONTEXT
    crypt32.CertDuplicateCertificateContext.argtypes = [PCCERT_CONTEXT]
    crypt32.CertDuplicateCertificateContext.restype = PCCERT_CONTEXT
    crypt32.CertFreeCertificateContext.argtypes = [PCCERT_CONTEXT]
    crypt32.CertFreeCertificateContext.restype = wintypes.BOOL
    crypt32.CertGetNameStringW.argtypes = [
        PCCERT_CONTEXT,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.LPWSTR,
        wintypes.DWORD,
    ]
    crypt32.CertGetNameStringW.restype = wintypes.DWORD
    crypt32.CertGetCertificateContextProperty.argtypes = [
        PCCERT_CONTEXT,
        wintypes.DWORD,
        wintypes.LPVOID,
        ctypes.POINTER(wintypes.DWORD),
    ]
    crypt32.CertGetCertificateContextProperty.restype = wintypes.BOOL
    return crypt32


def _open_windows_cert_store(crypt32: Any) -> wintypes.HANDLE:
    store = crypt32.CertOpenStore(
        SYSTEM_STORE_PROVIDER,
        0,
        None,
        CERT_SYSTEM_STORE_LOCAL_MACHINE | CERT_STORE_READONLY_FLAG,
        SYSTEM_STORE_ROOT,
    )
    if not store:
        raise OSError("Не удалось открыть хранилище сертификатов")
    return store


def _find_windows_cert_context(
    crypt32: Any,
    store: Any,
    ca_common_name: str,
) -> tuple[int, object | None]:
    match_count = 0
    first_context = None
    context = None
    encoding = X509_ASN_ENCODING | PKCS_7_ASN_ENCODING
    try:
        while True:
            context = crypt32.CertFindCertificateInStore(
                store,
                encoding,
                0,
                CERT_FIND_SUBJECT_STR_W,
                ctypes.c_wchar_p(ca_common_name),
                context,
            )
            if not context:
                break
            match_count += 1
            if match_count == 1:
                first_context = crypt32.CertDuplicateCertificateContext(context)
            if match_count >= MULTI_MATCH_THRESHOLD:
                break
    finally:
        if context:
            crypt32.CertFreeCertificateContext(context)
    return match_count, first_context


def _get_windows_cert_name(crypt32: Any, context: Any, flag: int) -> str:
    size = crypt32.CertGetNameStringW(
        context,
        CERT_NAME_SIMPLE_DISPLAY_TYPE,
        flag,
        None,
        None,
        0,
    )
    if size <= 1:
        return ""
    buffer = ctypes.create_unicode_buffer(size)
    crypt32.CertGetNameStringW(
        context,
        CERT_NAME_SIMPLE_DISPLAY_TYPE,
        flag,
        None,
        buffer,
        size,
    )
    return buffer.value


def _get_windows_cert_fingerprint(crypt32: Any, context: Any) -> str | None:
    hash_size = wintypes.DWORD(0)
    if not crypt32.CertGetCertificateContextProperty(
        context,
        CERT_SHA1_HASH_PROP_ID,
        None,
        ctypes.byref(hash_size),
    ):
        return None
    buf = (ctypes.c_ubyte * hash_size.value)()
    if not crypt32.CertGetCertificateContextProperty(
        context,
        CERT_SHA1_HASH_PROP_ID,
        buf,
        ctypes.byref(hash_size),
    ):
        return None
    return bytes(buf[: hash_size.value]).hex()


def _load_windows_cert_info(
    ca_common_name: str,
) -> tuple[int, list[dict[str, object]]]:
    crypt32 = _get_crypt32()
    store = _open_windows_cert_store(crypt32)
    try:
        match_count, first_context = _find_windows_cert_context(
            crypt32,
            store,
            ca_common_name,
        )
        if match_count != 1 or not first_context:
            if first_context:
                crypt32.CertFreeCertificateContext(first_context)
            return match_count, []

        subject = _get_windows_cert_name(crypt32, first_context, 0)
        issuer = _get_windows_cert_name(crypt32, first_context, CERT_NAME_ISSUER_FLAG)
        fingerprint = _get_windows_cert_fingerprint(crypt32, first_context)
        context = cast(Any, first_context)
        not_after_unix = _filetime_to_unix(context.contents.pCertInfo.contents.NotAfter)
        crypt32.CertFreeCertificateContext(first_context)

        cert: dict[str, object] = {
            "subject": subject,
            "issuer": issuer,
            "fingerprint_sha1": normalize_fingerprint(fingerprint),
            "not_after_unix": not_after_unix,
        }
        return match_count, [cert]
    finally:
        crypt32.CertCloseStore(store, 0)


def check_ca_cert(ca_common_name: str, log_func: LogFunc = print) -> OperationResult:
    """Проверить наличие указанного CA в системном хранилище доверия."""
    if is_macos():
        return _check_ca_on_macos(ca_common_name, log_func=log_func)
    if is_windows():
        return _check_ca_on_windows(ca_common_name, log_func=log_func)

    log_func("?? Текущая платформа не поддерживает автоматическую проверку системного "
        "CA-сертификата")
    return OperationResult.failure(
        "Текущая платформа не поддерживает автоматическую проверку системного CA-сертификата",
        exists=False,
    )


def install_ca_cert_file(ca_cert_file: str, log_func: LogFunc = print) -> OperationResult:
    """Установить указанный CA-сертификат в системное хранилище доверия."""
    if not ca_cert_file:
        return OperationResult.failure("Пустой путь к сертификату")

    if is_windows():
        return _install_ca_on_windows(ca_cert_file, log_func=log_func)
    if is_macos():
        return _install_ca_on_macos(ca_cert_file, log_func=log_func)
    if is_posix():
        return _install_ca_on_linux(ca_cert_file, log_func=log_func)

    log_func("Ошибка: неподдерживаемая операционная система")
    return OperationResult.failure("Неподдерживаемая операционная система")


def clear_ca_cert_store(ca_common_name: str, log_func: LogFunc = print) -> OperationResult:
    """Удалить указанный CA из системного хранилища доверия."""
    if is_macos():
        return _clear_ca_on_macos(ca_common_name, log_func=log_func)
    if is_windows():
        return _clear_ca_on_windows(ca_common_name, log_func=log_func)

    log_func("⚠️ Текущая платформа не поддерживает автоматическое удаление CA-сертификата")
    return OperationResult.failure("Текущая платформа не поддерживает автоматическое удаление "
        "CA-сертификата")


def _check_ca_on_windows(ca_common_name: str, log_func: LogFunc = print) -> OperationResult:
    log_func("Проверяем CA-сертификат в хранилище доверенных корневых сертификатов Windows...")
    try:
        match_count, certs = _load_windows_cert_info(ca_common_name)
    except Exception as exc:  # noqa: BLE001
        log_func(f"⚠️ Ошибка запроса сертификатов Windows: {exc}")
        return OperationResult.failure(
            "Не удалось прочитать хранилище сертификатов",
            exists=False,
        )

    if match_count > 1:
        log_func(f"Обнаружено совпадающих сертификатов: {match_count}; по правилам считаем "
            f"несовпадением")
        return OperationResult.success(
            exists=False,
            match_count=match_count,
            certs=[],
        )

    if certs:
        log_func("Обнаружен 1 совпадающий CA-сертификат")
        return OperationResult.success(
            exists=True,
            match_count=1,
            certs=certs,
        )

    log_func("Совпадающий CA-сертификат не найден")
    return OperationResult.success(exists=False, match_count=0, certs=[])


def _check_ca_on_macos(ca_common_name: str, log_func: LogFunc = print) -> OperationResult:
    log_func("Проверяем CA-сертификат в системной связке ключей macOS...")
    cmd = [
        "security",
        "find-certificate",
        "-a",
        "-c",
        ca_common_name,
        "-p",
        "/Library/Keychains/System.keychain",
    ]
    return_code, stdout, stderr = run_command(cmd)

    if (
        return_code == MAC_KEYCHAIN_ITEM_NOT_FOUND
        and stderr
        and "could not be found" in stderr.lower()
    ):
        log_func("Совпадающий CA-сертификат в системной связке ключей не найден")
        return OperationResult.success(exists=False)

    if return_code not in (0, MAC_KEYCHAIN_ITEM_NOT_FOUND):
        log_func(f"? Не удалось проверить системную связку ключей (код возврата: {return_code})")
        log_lines(stderr, log_func)
        return OperationResult.failure(
            "Не удалось проверить системную связку ключей",
            exists=False,
            returncode=return_code,
        )

    if not stdout.strip():
        log_func("Совпадающий CA-сертификат в системной связке ключей не найден")
        return OperationResult.success(exists=False, certs=[])

    certs: list[dict[str, object]] = []
    for pem_block in _split_pem_blocks(stdout):
        cert_info = _parse_pem_certificate(pem_block, log_func=log_func)
        if cert_info and cert_info.get("fingerprint_sha1"):
            certs.append(cert_info)

    if certs:
        log_func("В системной связке ключей обнаружен совпадающий CA-сертификат")
        return OperationResult.success(exists=True, match_count=len(certs), certs=certs)

    log_func("Совпадающий CA-сертификат в системной связке ключей не найден")
    return OperationResult.success(exists=False, certs=[])


def _install_ca_on_windows(ca_cert_file: str, log_func: LogFunc = print) -> OperationResult:
    log_func("Устанавливаем CA-сертификат в системе Windows...")
    cmd = f'certutil -addstore -f "ROOT" "{ca_cert_file}"'
    log_func(f"Выполняем команду: {cmd}")
    return_code, stdout, stderr = run_command(cmd, shell=True)

    log_lines(stdout, log_func)
    log_lines(stderr, log_func)

    if return_code == 0:
        log_func("CA-сертификат успешно установлен!")
        return OperationResult.success()

    log_func(f"Не удалось установить сертификат, код возврата: {return_code}")
    return OperationResult.failure(
        "Не удалось установить сертификат",
        returncode=return_code,
        stderr=stderr,
        stdout=stdout,
    )


def _install_ca_on_macos(ca_cert_file: str, log_func: LogFunc = print) -> OperationResult:
    log_func("Устанавливаем CA-сертификат в системе macOS...")
    session = get_mac_privileged_session(log_func=log_func)
    if not session:
        log_func("❌ Не удалось получить права администратора, сертификат не установлен")
        return OperationResult.failure("Не удалось получить права администратора")

    log_func("Запрашиваем права администратора для установки сертификата в системную связку ключей "
        "и пометки как доверенного...")
    success, data = session.install_trusted_cert(
        ca_cert_file,
        keychain="/Library/Keychains/System.keychain",
        log_func=log_func,
    )
    stdout = data.get("stdout")
    stderr = data.get("stderr")
    log_lines(stdout, log_func)
    log_lines(stderr, log_func)

    if success:
        log_func("✅ CA-сертификат добавлен в системную связку ключей и помечен как доверенный")
        return OperationResult.success()

    return_code = data.get("returncode")
    error_msg = ""
    error_msg = stderr or data.get("error") or ""
    log_func(
        
            f"❌ Не удалось установить сертификат (код возврата: "
            f"{return_code if return_code is not None else 'неизвестно'})"
        
    )
    if error_msg:
        log_func(f"Сообщение об ошибке: {error_msg}")
    return OperationResult.failure(
        "Не удалось установить сертификат",
        returncode=return_code,
        stderr=stderr,
        stdout=stdout,
    )


def _install_ca_on_linux(ca_cert_file: str, log_func: LogFunc = print) -> OperationResult:
    log_func("Устанавливаем CA-сертификат в системе Linux...")
    cmd = f'sudo cp "{ca_cert_file}" /usr/local/share/ca-certificates/'
    log_func(f"Выполняем команду: {cmd}")
    return_code, stdout, stderr = run_command(cmd, shell=True)

    log_lines(stdout, log_func)
    log_lines(stderr, log_func)

    if return_code != 0:
        log_func(f"Не удалось скопировать сертификат, код возврата: {return_code}")
        return OperationResult.failure(
            "Не удалось скопировать сертификат",
            returncode=return_code,
            stderr=stderr,
            stdout=stdout,
        )

    cmd = "sudo update-ca-certificates"
    log_func(f"Выполняем команду: {cmd}")
    return_code, stdout, stderr = run_command(cmd, shell=True)

    log_lines(stdout, log_func)
    log_lines(stderr, log_func)

    if return_code == 0:
        log_func("CA-сертификат успешно установлен!")
        return OperationResult.success()

    log_func(f"Не удалось обновить сертификаты, код возврата: {return_code}")
    return OperationResult.failure(
        "Не удалось обновить сертификаты",
        returncode=return_code,
        stderr=stderr,
        stdout=stdout,
    )


def _clear_ca_on_windows(ca_common_name: str, log_func: LogFunc = print) -> OperationResult:
    log_func("Начинаем удаление CA-сертификата из доверенных корневых Windows...")
    list_cmd = ["cmd", "/d", "/s", "/c", "certutil -store Root"]
    return_code, stdout, stderr = run_command(list_cmd)

    log_lines(stderr, log_func)
    if return_code != 0:
        log_func(f"❌ Не удалось прочитать хранилище сертификатов (код возврата: {return_code})")
        return OperationResult.failure(
            "Не удалось прочитать хранилище сертификатов",
            returncode=return_code,
        )

    entries = parse_certutil_store(stdout)
    targets = filter_certs_by_name(entries, ca_common_name)
    if not targets:
        log_func(f"Совпадающих сертификатов не найдено: {ca_common_name}")
        return OperationResult.success()

    log_func(f"Найдено совпадающих сертификатов: {len(targets)}, готовимся к удалению...")
    any_failed = False

    for cert in targets:
        thumbprint = cert.get("thumbprint")
        subject = cert.get("subject", "")
        if not thumbprint:
            any_failed = True
            log_func(f"⚠️ Пропускаем сертификат без хеша: {subject or '[неизвестный сертификат]'}")
            continue

        log_func(f"Deleting from Root store: {thumbprint}")
        if subject:
            log_func(f"Subject: {subject}")

        delete_cmd = ["cmd", "/d", "/s", "/c", f"certutil -delstore Root {thumbprint}"]
        rc, del_stdout, del_stderr = run_command(delete_cmd)
        log_lines(del_stdout, log_func)
        log_lines(del_stderr, log_func)
        if rc != 0:
            any_failed = True
            log_func(f"❌ Не удалось удалить (код возврата: {rc})")

    if any_failed:
        log_func("❌ Не удалось удалить CA-сертификат (часть сертификатов не удалена)")
        return OperationResult.failure("Часть сертификатов не удалена")

    log_func("✅ Удаление CA-сертификата завершено")
    return OperationResult.success()


def _clear_ca_on_macos(ca_common_name: str, log_func: LogFunc = print) -> OperationResult:
    session = get_mac_privileged_session(log_func=log_func)
    if not session:
        log_func("❌ Не удалось получить права администратора, удаление CA-сертификата невозможно")
        return OperationResult.failure("Не удалось получить права администратора")

    log_func("Начинаем удаление CA-сертификата из системной связки ключей...")
    command = (
        f"security find-certificate -a -c {shlex.quote(ca_common_name)} "
        "-Z /Library/Keychains/System.keychain "
        "| awk '/SHA-1 hash:/ {print $3}' "
        "| while read -r hash; do "
        'echo \"Deleting from System.keychain: $hash\"; '
        'sudo security delete-certificate -Z \"$hash\" /Library/Keychains/System.keychain; '
        "done"
    )
    success, data = session.run_command(["bash", "-lc", command], log_func=log_func)
    log_lines(data.get("stdout"), log_func)
    log_lines(data.get("stderr"), log_func)
    if success:
        log_func("✅ Удаление CA-сертификата завершено")
        return OperationResult.success()

    return_code = data.get("returncode")
    rc_text = return_code if return_code is not None else "неизвестно"
    log_func(f"❌ Не удалось удалить CA-сертификат (код возврата: {rc_text})")
    return OperationResult.failure(
        "Не удалось удалить CA-сертификат",
        returncode=return_code,
    )


__all__ = ["check_ca_cert", "clear_ca_cert_store", "install_ca_cert_file"]
