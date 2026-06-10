"""
Модуль управления путями ресурсов (единая реализация для tauri)
Обрабатывает пути к ресурсам в среде разработки и в упакованной среде tauri.
"""

import os
import shutil
import sys
import tempfile
from collections.abc import Callable
from importlib import resources
from pathlib import Path

from platformdirs import user_data_dir

# Переключатель пути ресурсов
# - MTGA_RESOURCE_DIR=... задаёт каталог ресурсов (высший приоритет)
# - если не задан — автоопределение: ресурсы пакета -> локальный modules/resources -> резервный
# каталог времени выполнения
RESOURCE_DIR = os.environ.get("MTGA_RESOURCE_DIR", "").strip()
LOGS_DIR_NAME = "logs"
LEGACY_USER_DATA_DIR_NAME = ".mtga"


def safe_print(message: object) -> None:
    """Print helper tolerant of non-ASCII stdout."""
    try:
        print(message)
    except UnicodeEncodeError:
        fallback = str(message).encode("unicode_escape").decode("ascii", errors="replace")
        print(fallback)


def _tauri_runtime_provider() -> str:
    runtime = os.environ.get("MTGA_RUNTIME", "").strip().lower()
    if runtime == "tauri":
        return "tauri"
    return "dev"


_PACKAGING_RUNTIME_PROVIDER: dict[str, Callable[[], str]] = {
    "provider": _tauri_runtime_provider
}


def set_packaging_runtime_provider(provider: Callable[[], str]) -> None:
    """Внедрить логику определения рантайма. По умолчанию — tauri/dev."""
    _PACKAGING_RUNTIME_PROVIDER["provider"] = provider


def get_packaging_runtime() -> str:
    """Определить тип рантайма: tauri / dev."""
    return _PACKAGING_RUNTIME_PROVIDER["provider"]()


def is_packaged() -> bool:
    """Проверить, выполняется ли код в упакованной среде (tauri)."""
    return get_packaging_runtime() != "dev"


def get_user_data_dir() -> str:
    """Получить каталог пользовательских данных для постоянного хранения."""
    app_name = "MTGA"
    roaming = os.name == "nt"
    platform_dir = user_data_dir(app_name, appauthor=False, roaming=roaming)

    os.makedirs(platform_dir, exist_ok=True)
    return platform_dir


def get_legacy_user_data_dir() -> str:
    """Получить путь к устаревшему каталогу пользовательских данных."""
    return os.path.join(os.path.expanduser("~"), LEGACY_USER_DATA_DIR_NAME)


def has_legacy_user_data_dir() -> bool:
    """Проверить, существует ли устаревший каталог с возможными старыми данными."""
    if os.name == "nt":
        return False
    legacy_dir = get_legacy_user_data_dir()
    if not os.path.isdir(legacy_dir):
        return False
    try:
        return len(os.listdir(legacy_dir)) > 0
    except Exception:
        return True


def _get_packaged_resource_dir() -> str | None:
    try:
        base = resources.files("modules") / "resources"
        if base.is_dir():
            with resources.as_file(base) as path:
                return str(path)
    except Exception:
        return None
    return None


def _get_local_resource_dir() -> str | None:
    path = Path(__file__).resolve().parent.parent / "resources"
    if path.is_dir():
        return str(path)
    return None


def get_program_resource_dir() -> str:
    """Получить каталог ресурсов программы (шаблоны конфигурации и т. п.)"""
    runtime = get_packaging_runtime()
    override_dir = RESOURCE_DIR
    packaged_dir = _get_packaged_resource_dir()
    local_dir = _get_local_resource_dir()
    resource_dir = override_dir or packaged_dir or local_dir
    if resource_dir:
        return resource_dir

    if runtime == "dev":
        # В среде разработки используется корень проекта
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    exe_dir = os.path.dirname(sys.executable)
    # В упакованной среде tauri используется каталог исполняемого файла
    return exe_dir


def get_base_path() -> str:
    """Получить базовый путь программы (совместимость со старым API)"""
    return get_program_resource_dir()


def get_resource_path(relative_path: str) -> str:
    """
    Получить абсолютный путь к файлу ресурсов программы (шаблоны конфигурации и т. п.)

    Параметры:
        relative_path: путь относительно каталога ресурсов программы

    Возвращает:
        строку с абсолютным путём
    """
    base_path = get_program_resource_dir()
    return os.path.join(base_path, relative_path)


def get_user_data_path(relative_path: str) -> str:
    """
    Получить абсолютный путь к файлу пользовательских данных (
        конфигурация, сертификаты, резервные копии и т. п.
    )

    Параметры:
        relative_path: путь относительно каталога пользовательских данных

    Возвращает:
        строку с абсолютным путём
    """
    user_dir = get_user_data_dir()
    return os.path.join(user_dir, relative_path)


def get_logs_dir() -> str:
    """Получить путь к каталогу логов (каталог пользовательских данных/logs)."""
    logs_dir = get_user_data_path(LOGS_DIR_NAME)
    os.makedirs(logs_dir, exist_ok=True)
    return logs_dir


def get_log_path(filename: str) -> str:
    """Получить путь к файлу лога (каталог пользовательских данных/logs)."""
    return os.path.join(get_logs_dir(), filename)


def get_ca_path() -> str:
    """Получить путь к каталогу CA (каталог пользовательских данных)"""
    return get_user_data_path("ca")


def get_ca_template_path() -> str:
    """Получить путь к каталогу шаблонов конфигурации CA (каталог ресурсов программы)"""
    return get_resource_path("ca")


def get_temp_dir() -> str:
    """Получить каталог временных файлов"""
    return tempfile.gettempdir()


def ensure_directory_exists(path: str) -> None:
    """Убедиться, что каталог существует; создать при необходимости"""
    os.makedirs(path, exist_ok=True)


def copy_template_files() -> list[str]:
    """Скопировать шаблоны конфигурации в каталог пользовательских данных"""
    template_ca_dir = get_ca_template_path()
    user_ca_dir = get_ca_path()

    # Убедиться, что пользовательский каталог CA существует
    ensure_directory_exists(user_ca_dir)

    # Шаблоны, которые нужно скопировать
    template_files = [
        "README.md",
        "api.openai.com.cnf",
        "api.openai.com.subj",
        "genca.sh",
        "gencrt.sh",
        "google.cnf",
        "google.subj",
        "openssl.cnf",
        "pixiv.cnf",
        "pixiv.subj",
        "v3_ca.cnf",
        "v3_req.cnf",
        "youtube.cnf",
        "youtube.subj",
    ]

    copied_files: list[str] = []
    for filename in template_files:
        src_path = os.path.join(template_ca_dir, filename)
        dst_path = os.path.join(user_ca_dir, filename)

        # Копируем только если целевого файла ещё нет
        if os.path.exists(src_path) and not os.path.exists(dst_path):
            try:
                shutil.copy2(src_path, dst_path)
                copied_files.append(filename)
            except Exception:
                pass

    return copied_files


class ResourceManager:
    """Класс менеджера ресурсов: единый интерфейс доступа к ресурсам"""

    def __init__(self) -> None:
        self.program_resource_dir = get_program_resource_dir()
        self.user_data_dir = get_user_data_dir()
        self.ca_path = get_ca_path()
        self.ca_template_path = get_ca_template_path()

        # При инициализации копируем шаблоны
        self._ensure_user_data_setup()

    def _ensure_user_data_setup(self) -> None:
        """Убедиться, что каталог пользовательских данных настроен корректно"""
        # Копируем шаблоны конфигурации в пользовательский каталог
        copied_files = copy_template_files()
        if copied_files:
            safe_print(f"Шаблоны скопированы в пользовательский каталог: {', '.join(copied_files)}")

    @property
    def base_path(self) -> str:
        """Базовый путь (совместимость со старым API)"""
        return self.program_resource_dir

    def get_cert_file(self, domain: str = "api.openai.com") -> str:
        """Получить путь к файлу сертификата (каталог пользовательских данных)"""
        return os.path.join(self.ca_path, f"{domain}.crt")

    def get_key_file(self, domain: str = "api.openai.com") -> str:
        """Получить путь к файлу закрытого ключа (каталог пользовательских данных)"""
        return os.path.join(self.ca_path, f"{domain}.key")

    def get_ca_cert_file(self) -> str:
        """Получить путь к файлу CA-сертификата (каталог пользовательских данных)"""
        return os.path.join(self.ca_path, "ca.crt")

    def get_ca_key_file(self) -> str:
        """Получить путь к файлу закрытого ключа CA (каталог пользовательских данных)"""
        return os.path.join(self.ca_path, "ca.key")

    def get_ca_info_file(self) -> str:
        """Получить путь к файлу метаданных CA (каталог пользовательских данных)"""
        return os.path.join(self.ca_path, "ca_info.json")

    def get_config_file(self, filename: str) -> str:
        """Получить путь к файлу конфигурации (каталог пользовательских данных)"""
        return os.path.join(self.ca_path, filename)

    def get_icon_file(self, filename: str) -> str:
        """Получить путь к файлу иконки (каталог ресурсов программы)"""
        return os.path.join(self.program_resource_dir, "icons", filename)

    def get_user_config_file(self) -> str:
        """Получить путь к файлу пользовательской конфигурации"""
        return get_user_data_path("mtga_config.yaml")

    def get_hosts_backup_file(self) -> str:
        """Получить путь к файлу резервной копии hosts"""
        return get_user_data_path("hosts.backup")

    def get_logs_dir(self) -> str:
        """Получить путь к каталогу логов"""
        return get_logs_dir()

    def get_log_file(self, filename: str) -> str:
        """Получить путь к файлу лога"""
        return get_log_path(filename)

    def check_resources(self) -> list[str]:
        """Проверить наличие необходимых ресурсов"""
        missing_resources: list[str] = []

        # Отладочная информация
        debug_info: list[str] = []
        debug_info.append(f"Текущий рабочий каталог: {os.getcwd()}")
        debug_info.append(f"Каталог ресурсов программы: {self.program_resource_dir}")
        debug_info.append(f"Каталог пользовательских данных: {self.user_data_dir}")
        debug_info.append(f"Каталог CA: {self.ca_path}")
        debug_info.append("Бэкенд генерации сертификатов: cryptography")
        debug_info.append(f"Среда выполнения: {get_packaging_runtime()}")

        # В упакованной среде выводим дополнительную отладочную информацию
        if is_packaged():
            debug_info.append(f"Путь к исполняемому файлу: {sys.executable}")
            main_module = sys.modules.get("__main__")
            if main_module is not None:
                main_file = getattr(main_module, "__file__", None)
                if isinstance(main_file, str):
                    debug_info.append(f"Путь к файлу главного модуля: {main_file}")

        # Вывод отладочной информации
        safe_print("=== Отладочная информация о путях ресурсов ===")
        for info in debug_info:
            safe_print(info)
        safe_print("=" * 30)

        # Проверка каталога CA (каталог пользовательских данных)
        if not os.path.exists(self.ca_path):
            missing_resources.append(f"Каталог CA: {self.ca_path}")

        return missing_resources
