from __future__ import annotations

from collections.abc import Callable


def check_environment(*, check_resources: Callable[[], list[str]]) -> tuple[bool, str]:
    """Проверяет, что все ресурсы, необходимые среде выполнения, на месте."""
    missing_resources = check_resources()

    if missing_resources:
        error_msg = "Проверка окружения не пройдена, отсутствуют ресурсы:\n" + "\n".join(
            missing_resources
        )
        return False, error_msg

    return True, "Проверка окружения пройдена"
