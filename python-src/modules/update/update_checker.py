"""Обёртка над запросом последней версии с GitHub и логикой сравнения версий."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, cast

import requests

_SEMVER_PATTERN = re.compile(
    r"v?(?P<version>\d+(?:\.\d+)*)(?:-(?P<prerelease>[0-9a-z-]+(?:\.[0-9a-z-]+)*))?",
    re.IGNORECASE,
)
_G_EMOJI_PATTERN = re.compile(
    r"<g-emoji\b(?P<attrs>[^>]*)>(?P<content>.*?)</g-emoji>",
    re.IGNORECASE | re.DOTALL,
)
_EMOJI_SHORTCODE_PATTERN = re.compile(r":(?P<name>[a-z0-9_+-]+):", re.IGNORECASE)
_IMG_TAG_PATTERN = re.compile(r"<img\b(?P<attrs>[^>]*?)\s*/?>", re.IGNORECASE | re.DOTALL)


@dataclass(slots=True)
class HtmlFontOptions:
    family: str | None = None
    size: int | None = None
    weight: str | None = None


@dataclass(slots=True)
class ReleaseInfo:
    """Основная информация о последнем релизе GitHub."""

    version_label: str | None
    release_notes: str
    release_url: str


def render_markdown_via_github_api(
    markdown_text: str | None,
    *,
    repo: str,
    timeout: int = 10,
    user_agent: str | None = None,
    font: HtmlFontOptions | None = None,
) -> str:
    """Вызывает GitHub /markdown API для рендеринга Markdown в HTML.

    Примечания:
    - API возвращает HTML-фрагмент; здесь он оборачивается в полный HTML-документ
      для прямого load_html в GUI.
    - Опционально внедряется минимальный CSS только для шрифтов
      (чтобы использовать глобальные настройки шрифта GUI).
    - При сбое рендеринга выполняется откат к простому тексту в <pre>.
    """
    safe_source = _replace_emoji_shortcodes_with_img(
        markdown_text or "",
        timeout=timeout,
        user_agent=user_agent,
    )

    font_family = font.family if font else None
    font_size = font.size if font else None
    font_weight = font.weight if font else None

    escaped_family = (font_family or "").replace('"', r"\"").strip()
    font_stack = (
        f'"{escaped_family}", "Maple Mono NF CN", "Microsoft YaHei UI", "Microsoft YaHei", '
        '"PingFang SC", "Hiragino Sans GB", "Segoe UI", "Arial", sans-serif'
        if escaped_family
        else '"Maple Mono NF CN", "Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", '
        '"Hiragino Sans GB", "Segoe UI", "Arial", sans-serif'
    )
    css_rules: list[str] = []
    if font_family:
        css_rules.append(f"font-family: {font_stack};")
    if font_size:
        css_rules.append(f"font-size: {int(font_size)}px;")
    if font_weight:
        css_rules.append(f"font-weight: {font_weight};")
    style_chunks: list[str] = []
    if css_rules:
        style_chunks.append(f"body{{{''.join(css_rules)}}}")
    style_chunks.append("img.g-emoji{height:1em;width:1em;}")
    base_style = f"<style>{''.join(style_chunks)}</style>" if style_chunks else ""
    headers = {
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    }
    if user_agent:
        headers["User-Agent"] = user_agent

    try:
        response = requests.post(
            "https://api.github.com/markdown",
            json={"text": safe_source, "mode": "gfm", "context": repo},
            timeout=timeout,
            headers=headers,
        )
        if response.status_code == requests.codes.ok:  # type: ignore[attr-defined]
            rendered_fragment = response.text or ""
            rendered_fragment = _replace_g_emoji_with_img(rendered_fragment)
            rendered_fragment = _style_emoji_images(rendered_fragment)
            return "".join(
                (
                    "<html><head><meta charset='utf-8'>",
                    base_style,
                    "</head><body>",
                    rendered_fragment,
                    "</body></html>",
                )
            )
    except requests.RequestException:
        pass

    return "".join(
        (
            "<html><head><meta charset='utf-8'>",
            base_style,
            "</head><body><pre>",
            html.escape(safe_source),
            "</pre></body></html>",
        )
    )


def _replace_g_emoji_with_img(rendered_html: str) -> str:
    """Преобразует GitHub <g-emoji> в <img>, чтобы избежать пустых мест из-за отсутствия шрифта."""

    def _extract_attr(attrs: str, name: str) -> str | None:
        match = re.search(rf'{name}=(["\'])(?P<value>.*?)\1', attrs, re.IGNORECASE)
        if not match:
            return None
        return match.group("value")

    def _replace(match: re.Match[str]) -> str:
        attrs = match.group("attrs")
        content = match.group("content").strip()
        fallback_src = _extract_attr(attrs, "fallback-src")
        if not fallback_src:
            return match.group(0)
        alias = _extract_attr(attrs, "alias")
        alt_text = html.escape((alias or content or "").strip(), quote=True)
        return f'<img src="{fallback_src}" alt="{alt_text}" class="g-emoji">'

    return _G_EMOJI_PATTERN.sub(_replace, rendered_html)


def _style_emoji_images(rendered_html: str) -> str:
    """Добавляет emoji-изображениям размеры и выравнивание, приближая отображение к GitHub."""

    def _extract_attr(attrs: str, name: str) -> str | None:
        match = re.search(rf'{name}=(["\'])(?P<value>.*?)\1', attrs, re.IGNORECASE)
        if not match:
            return None
        return match.group("value")

    def _replace_or_add_attr(attrs: str, name: str, value: str) -> str:
        if re.search(rf'{name}=(["\'])', attrs, re.IGNORECASE):
            return re.sub(
                rf'{name}=(["\'])(?P<value>.*?)\1',
                f'{name}="{value}"',
                attrs,
                flags=re.IGNORECASE | re.DOTALL,
            )
        return f"{attrs} {name}=\"{value}\""

    def _is_github_emoji(attrs: str) -> bool:
        data_canonical_src = _extract_attr(attrs, "data-canonical-src")
        src = _extract_attr(attrs, "src")
        if data_canonical_src and "/images/icons/emoji/" in data_canonical_src:
            return True
        if src and "/images/icons/emoji/" in src:
            return True
        if src and "camo.githubusercontent.com" in src:
            return bool(data_canonical_src and "/images/icons/emoji/" in data_canonical_src)
        return False

    def _replace(match: re.Match[str]) -> str:
        attrs = match.group("attrs").strip()
        if not _is_github_emoji(attrs):
            return match.group(0)
        style_value = _extract_attr(attrs, "style") or ""
        style_value = re.sub(
            r"vertical-align\s*:\s*[^;]+;?",
            "",
            style_value,
            flags=re.IGNORECASE,
        )
        style_suffix = "height:1em;width:1em;"
        if style_suffix not in style_value:
            style_value = f"{style_value.rstrip(';')};{style_suffix}".lstrip(";")
        new_attrs = _replace_or_add_attr(attrs, "style", style_value)
        return f"<img {new_attrs}>"

    return _IMG_TAG_PATTERN.sub(_replace, rendered_html)


def _replace_emoji_shortcodes_with_img(
    markdown_text: str,
    *,
    timeout: int,
    user_agent: str | None,
) -> str:
    """Заменяет :shortcode: на <img>, чтобы избежать отсутствия emoji-шрифта."""
    emoji_urls = _get_emoji_urls(timeout=timeout, user_agent=user_agent)
    if not emoji_urls:
        return markdown_text

    def _replace(match: re.Match[str]) -> str:
        name = match.group("name")
        url = emoji_urls.get(name)
        if not url:
            return match.group(0)
        alt_text = f":{name}:"
        return f'<img src="{url}" alt="{alt_text}" class="g-emoji">'

    return _EMOJI_SHORTCODE_PATTERN.sub(_replace, markdown_text)


@lru_cache(maxsize=8)
def _get_emoji_urls(*, timeout: int, user_agent: str | None) -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json"}
    if user_agent:
        headers["User-Agent"] = user_agent

    try:
        response = requests.get(
            "https://api.github.com/emojis",
            timeout=timeout,
            headers=headers,
        )
        if response.status_code == requests.codes.ok:  # type: ignore[attr-defined]
            data = response.json()
            if isinstance(data, dict):
                data_dict = cast(dict[str, Any], data)
                return {str(k): str(v) for k, v in data_dict.items()}
    except requests.RequestException:
        pass

    return {}


def _normalize_version_tuple(version_text: str | None) -> tuple[int, ...]:
    """Преобразует строку версии в кортеж целых чисел для сравнения."""
    if not version_text:
        return ()
    match = _SEMVER_PATTERN.search(version_text.strip())
    if not match:
        return ()
    numeric_part = match.group("version")
    tokens: list[int] = []
    for chunk in numeric_part.split("."):
        digits = re.match(r"\d+", chunk)
        if not digits:
            continue
        tokens.append(int(digits.group()))
    return tuple(tokens)


def _parse_prerelease(version_text: str | None) -> tuple[int | str, ...] | None:
    """Разбирает prerelease-идентификатор semver и возвращает список токенов для сравнения."""
    if not version_text:
        return None
    match = _SEMVER_PATTERN.search(version_text.strip())
    if not match:
        return None
    prerelease = match.group("prerelease")
    if not prerelease:
        return None

    tokens: list[int | str] = []
    for token in prerelease.split("."):
        if token.isdigit():
            tokens.append(int(token))
        else:
            tokens.append(token.lower())
    return tuple(tokens)


def _compare_prerelease(
    remote_prerelease: tuple[int | str, ...],
    local_prerelease: tuple[int | str, ...],
) -> int:
    """Сравнивает prerelease по правилам SemVer, возвращает 1/0/-1."""
    for remote_token, local_token in zip(remote_prerelease, local_prerelease, strict=False):
        if remote_token == local_token:
            continue

        remote_is_num = isinstance(remote_token, int)
        local_is_num = isinstance(local_token, int)
        if remote_is_num and local_is_num:
            return 1 if remote_token > local_token else -1
        if remote_is_num != local_is_num:
            # SemVer: числовые идентификаторы имеют меньший приоритет, чем нечисловые.
            return -1 if remote_is_num else 1

        remote_text = str(remote_token)
        local_text = str(local_token)
        return 1 if remote_text > local_text else -1

    if len(remote_prerelease) == len(local_prerelease):
        return 0
    return 1 if len(remote_prerelease) > len(local_prerelease) else -1


def extract_version_label(text: str | None) -> str | None:
    """Извлекает фрагмент вида vX.Y.Z из заголовка или тега."""
    if not text:
        return None
    match = _SEMVER_PATTERN.search(text.strip())
    if not match:
        return None
    version = match.group(0)
    if not version.lower().startswith("v"):
        version = f"v{version}"
    return version


def is_remote_version_newer(remote_version: str | None, local_version: str | None) -> bool:
    """Сравнивает удалённую и локальную версии, поддерживает prerelease (например -beta.1)."""
    remote_tuple = _normalize_version_tuple(remote_version)
    local_tuple = _normalize_version_tuple(local_version)
    if not remote_tuple:
        return False
    if not local_tuple:
        return True

    if remote_tuple[0] != local_tuple[0]:
        return remote_tuple[0] > local_tuple[0]
    if remote_tuple != local_tuple:
        return remote_tuple > local_tuple

    remote_prerelease = _parse_prerelease(remote_version)
    local_prerelease = _parse_prerelease(local_version)
    # При одинаковой числовой версии: релиз > prerelease.
    if remote_prerelease is None or local_prerelease is None:
        return remote_prerelease is None and local_prerelease is not None
    return _compare_prerelease(remote_prerelease, local_prerelease) > 0


def fetch_latest_release(
    repo: str,
    *,
    timeout: int = 10,
    user_agent: str | None = None,
    font: HtmlFontOptions | None = None,
) -> ReleaseInfo:
    """Получает информацию о последнем релизе через GitHub API."""
    if not repo:
        raise ValueError("repo не может быть пустым")
    api_url = f"https://api.github.com/repos/{repo}/releases/latest"
    headers = {"Accept": "application/vnd.github+json"}
    if user_agent:
        headers["User-Agent"] = user_agent

    response = requests.get(api_url, timeout=timeout, headers=headers)
    if response.status_code != requests.codes.ok:  # type: ignore[attr-defined]
        raise RuntimeError(f"GitHub вернул {response.status_code}")

    data = response.json()
    version_label = extract_version_label(data.get("name")) or extract_version_label(
        data.get("tag_name")
    )
    release_notes = render_markdown_via_github_api(
        data.get("body") or "",
        repo=repo,
        timeout=timeout,
        user_agent=user_agent,
        font=font,
    )
    release_url = data.get("html_url") or ""
    return ReleaseInfo(
        version_label=version_label,
        release_notes=release_notes,
        release_url=release_url,
    )


__all__ = [
    "HtmlFontOptions",
    "ReleaseInfo",
    "extract_version_label",
    "is_remote_version_newer",
    "fetch_latest_release",
    "render_markdown_via_github_api",
]
