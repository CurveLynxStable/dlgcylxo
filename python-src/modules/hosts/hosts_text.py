from __future__ import annotations

from collections.abc import Iterable
from typing import cast

HOSTS_ENTRY_MARKER = "# Added by MTGA"
DEFAULT_HOSTS_IPS: tuple[str, str] = ("127.0.0.1", "::1")


def normalize_ip_list(ip: str | Iterable[object] | object | None) -> list[str]:
    """Преобразует параметр IP в список строк без дубликатов."""
    iterable: Iterable[object]
    if ip is None:
        iterable = DEFAULT_HOSTS_IPS
    elif isinstance(ip, str):
        iterable = [ip]
    elif isinstance(ip, Iterable):
        iterable = cast(Iterable[object], ip)
    else:
        iterable = [ip]

    normalized: list[str] = []
    for addr in iterable:
        if not addr:
            continue
        addr_str = str(addr).strip()
        if addr_str and addr_str not in normalized:
            normalized.append(addr_str)
    return normalized


def build_hosts_block(domain: object, ip_list: list[str]) -> str:
    """Строит единый текстовый блок hosts по домену и списку IP."""
    domain = str(domain).strip()
    valid_ips = [ip for ip in ip_list if ip]
    if not domain or not valid_ips:
        return ""
    entries = "\n".join(f"{ip} {domain}" for ip in valid_ips)
    return f"{HOSTS_ENTRY_MARKER}\n{entries}\n"


def append_hosts_block(content: str, hosts_block: str) -> str:
    """Дозаписывает текстовый блок hosts после исходного содержимого, сохраняя пустую
    строку-разделитель."""
    content = content.rstrip("\n")
    if not content:
        return hosts_block
    return f"{content}\n\n{hosts_block}"


def remove_legacy_hosts_entries(content: str, domain: str) -> tuple[str, int]:
    """
    Удаляет записи hosts старого формата (записывались по одной),
    возвращает новое содержимое и число удалённых.
    Старый формат — один комментарий с одной записью домена.
    """
    lines = content.splitlines()
    new_lines: list[str] = []
    skip_block = False
    removed_entries = 0

    for line in lines:
        if skip_block:
            if domain in line:
                removed_entries += 1
                continue
            if not line.strip():
                skip_block = False
                continue
            skip_block = False
        if HOSTS_ENTRY_MARKER in line:
            if new_lines and not new_lines[-1].strip():
                new_lines.pop()
            skip_block = True
            continue
        new_lines.append(line)

    trailing_newline = content.endswith("\n")
    new_content = "\n".join(new_lines)
    if trailing_newline:
        new_content += "\n"
    return new_content, removed_entries


def remove_hosts_block_from_content(
    content: str, domain: str, ip_list: str | Iterable[object] | object | None
) -> tuple[str, int]:
    """Удаляет текстовый блок текущей версии и возвращает новое содержимое и число удалённых
    записей."""
    normalized_ips = normalize_ip_list(ip_list)
    removed_entries = 0
    block_text = build_hosts_block(domain, normalized_ips)

    if block_text:
        variants = [
            ("\n\n" + block_text, "\n"),
            ("\n" + block_text, "\n"),
            (block_text, ""),
        ]
        for target, replacement in variants:
            while target in content:
                content = content.replace(target, replacement, 1)
                removed_entries += len(normalized_ips)

    content, legacy_removed = remove_legacy_hosts_entries(content, domain)
    removed_entries += legacy_removed
    return content, removed_entries


__all__ = [
    "DEFAULT_HOSTS_IPS",
    "HOSTS_ENTRY_MARKER",
    "append_hosts_block",
    "build_hosts_block",
    "normalize_ip_list",
    "remove_hosts_block_from_content",
    "remove_legacy_hosts_entries",
]
