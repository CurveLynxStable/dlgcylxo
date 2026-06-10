from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from modules.runtime.error_codes import ErrorCode
from modules.runtime.result_messages import describe_result


@dataclass
class UpdateCheckState:
    task_id: Any | None = None


@dataclass
class UpdateCheckController:
    state: UpdateCheckState
    deps: UpdateCheckDeps | None = None

    def configure(self, deps: UpdateCheckDeps) -> None:
        self.deps = deps

    def trigger(self) -> None:
        if self.deps is None:
            return
        run_update_check(deps=self.deps, state=self.state)


@dataclass(frozen=True)
class UpdateCheckDeps:
    window: Any
    log: Callable[[str], None]
    thread_manager: Any
    check_button: Any | None
    app_display_name: str
    app_version: str
    repo: str
    default_font: Any
    update_service: Any
    update_dialog: Any
    messagebox: Any
    create_tkinterweb_html_widget: Callable[..., Any]
    program_resource_dir: str


def run_update_check(*, deps: UpdateCheckDeps, state: UpdateCheckState) -> None:
    if deps.check_button:
        deps.check_button.state(["disabled"])

    def finalize(callback: Callable[[], None]) -> None:
        def _finish() -> None:
            if deps.check_button:
                deps.check_button.state(["!disabled"])
            callback()

        deps.window.after(0, _finish)

    def worker() -> None:
        def show_error(title: str, message: str) -> None:
            deps.messagebox.showerror(title, message)
            deps.log(message)

        result = deps.update_service.check_for_updates_result(
            repo=deps.repo,
            app_version=deps.app_version,
            timeout=10,
            user_agent=f"{deps.app_display_name}/{deps.app_version}",
            font=deps.update_service.UpdateFontOptions(
                family=deps.default_font.cget("family"),
                size=int(deps.default_font.cget("size")),
                weight=deps.default_font.cget("weight"),
            ),
        )

        update_result = result.details.get("update_result") if result.details else None
        status = getattr(update_result, "status", None) if update_result else None

        if not result.ok:
            if result.code == ErrorCode.NO_VERSION or status == "no_version":
                def _warn_no_version() -> None:
                    deps.messagebox.showwarning("Проверка обновлений", "Не удалось разобрать номер "
                        "последней версии, повторите попытку позже.")
                    deps.log("Проверка обновлений не удалась: не удалось разобрать номер версии")

                finalize(_warn_no_version)
                return

            error_msg = describe_result(result, "Проверка обновлений не удалась")
            finalize(lambda: show_error("Проверка обновлений не удалась", error_msg))
            return

        if status == "up_to_date":
            def _info_up_to_date() -> None:
                deps.messagebox.showinfo(
                    "Проверка обновлений", f"Текущая версия {deps.app_version} — последняя."
                )
                deps.log("Проверка обновлений: установлена последняя версия")

            finalize(_info_up_to_date)
            return

        if not update_result:
            finalize(lambda: show_error("Проверка обновлений не удалась", "Не удалось разобрать "
                "результат обновления"))
            return

        latest_version = update_result.latest_version or "неизвестная версия"
        release_notes = update_result.release_notes or "Для этой версии нет описания изменений."
        release_url = update_result.release_url or ""

        def _show_new_version() -> None:
            deps.update_dialog.show_release_notes_dialog(
                deps.update_dialog.UpdateDialogDeps(
                    window=deps.window,
                    notes_html=release_notes,
                    release_url=release_url,
                    version_label=latest_version,
                    create_tkinterweb_html_widget=deps.create_tkinterweb_html_widget,
                    program_resource_dir=deps.program_resource_dir,
                    log=deps.log,
                )
            )
            deps.log(f"Доступна новая версия: {latest_version}")

        finalize(_show_new_version)

    state.task_id = deps.thread_manager.run("check_updates", worker)
