"""Runner preflight checks for config, paths, secrets, and optional deps."""

from __future__ import annotations

import importlib.util
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable


_SENSITIVE_KEY_PARTS = ("api_key", "token", "secret", "password")
_PLACEHOLDER_MARKERS = (
    "your_",
    "change_me",
    "placeholder",
    "example",
    "sample",
    "dummy",
    "replace_me",
)


@dataclass
class DoctorIssue:
    level: str
    code: str
    message: str
    setting: str | None = None
    resolved_path: str | None = None
    fix: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DoctorReport:
    config_path: str | None
    validation_mode: str
    issues: list[DoctorIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[DoctorIssue]:
        return [issue for issue in self.issues if issue.level == "error"]

    @property
    def warnings(self) -> list[DoctorIssue]:
        return [issue for issue in self.issues if issue.level == "warning"]

    @property
    def infos(self) -> list[DoctorIssue]:
        return [issue for issue in self.issues if issue.level == "info"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "config_path": self.config_path,
            "validation_mode": self.validation_mode,
            "errors": [issue.to_dict() for issue in self.errors],
            "warnings": [issue.to_dict() for issue in self.warnings],
            "infos": [issue.to_dict() for issue in self.infos],
        }


def _add_issue(
    report: DoctorReport,
    level: str,
    code: str,
    message: str,
    *,
    setting: str | None = None,
    resolved_path: Path | None = None,
    fix: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    report.issues.append(
        DoctorIssue(
            level=level,
            code=code,
            message=message,
            setting=setting,
            resolved_path=str(resolved_path) if resolved_path is not None else None,
            fix=fix,
            detail=detail or {},
        )
    )


def _module_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def _looks_like_placeholder_secret(value: str) -> bool:
    normalized = value.strip().lower()
    if not normalized:
        return True
    if any(marker in normalized for marker in _PLACEHOLDER_MARKERS):
        return True
    if normalized.startswith("<") and normalized.endswith(">"):
        return True
    if value.isupper() and any(part in normalized for part in ("key", "token", "secret", "password")):
        return True
    return False


def _iter_secret_candidates(node: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[str, str]]:
    if isinstance(node, dict):
        for key, value in node.items():
            if str(key).startswith("_"):
                continue
            next_path = (*path, str(key))
            if isinstance(value, dict):
                yield from _iter_secret_candidates(value, next_path)
                continue
            lowered = str(key).lower()
            if isinstance(value, str) and any(part in lowered for part in _SENSITIVE_KEY_PARTS):
                yield ".".join(next_path), value


def _resolve_path(base_dir: Path, value: str) -> Path:
    candidate = Path(value)
    return candidate if candidate.is_absolute() else (base_dir / candidate)


def _config_base_dir(config_path: Path | None) -> Path:
    if config_path is None:
        return Path.cwd()
    if config_path.parent.name == "config":
        return config_path.parent.parent
    return config_path.parent


def _check_directory(report: DoctorReport, base_dir: Path, setting: str, value: str) -> None:
    resolved = _resolve_path(base_dir, value)
    if resolved.exists() and not resolved.is_dir():
        _add_issue(
            report,
            "error",
            "path-not-directory",
            f"Configured directory setting points to a file: {resolved}",
            setting=setting,
            resolved_path=resolved,
            fix="Point the setting at a directory path.",
        )
    elif not resolved.exists():
        _add_issue(
            report,
            "warning",
            "missing-directory",
            f"Configured directory does not exist yet: {resolved}",
            setting=setting,
            resolved_path=resolved,
            fix="Create the directory or let the pipeline create it before relying on it.",
        )


def _check_input_file(
    report: DoctorReport,
    base_dir: Path,
    setting: str,
    value: str,
    *,
    required: bool,
) -> None:
    if not value:
        if required:
            _add_issue(
                report,
                "error",
                "missing-path",
                "Required path setting is empty.",
                setting=setting,
                fix="Set the path explicitly in the active config.",
            )
        return

    resolved = _resolve_path(base_dir, value)
    if not resolved.exists():
        _add_issue(
            report,
            "error" if required else "warning",
            "missing-path",
            f"Configured path does not exist: {resolved}",
            setting=setting,
            resolved_path=resolved,
            fix="Create the file or update the config to a valid path.",
        )


def _check_output_path(report: DoctorReport, base_dir: Path, setting: str, value: str) -> None:
    if not value:
        return
    resolved = _resolve_path(base_dir, value)
    parent = resolved.parent
    if not parent.exists():
        _add_issue(
            report,
            "warning",
            "missing-output-parent",
            f"Output parent directory does not exist yet: {parent}",
            setting=setting,
            resolved_path=resolved,
            fix="Create the parent directory or allow the command to create it during execution.",
        )


def _check_paths(report: DoctorReport, config: dict[str, Any], base_dir: Path) -> None:
    paths_cfg = config.get("paths") or {}
    for key in ("data_root", "raw_dir", "cleaned_dir", "filtered_dir", "log_dir", "metadata_dir", "cache_dir"):
        value = paths_cfg.get(key)
        if isinstance(value, str) and value.strip():
            _check_directory(report, base_dir, f"paths.{key}", value)

    scraping_cfg = config.get("scraping") or {}
    web_crawler_cfg = scraping_cfg.get("web_crawler") or {}
    if isinstance(web_crawler_cfg, dict) and web_crawler_cfg.get("enabled"):
        _check_input_file(
            report,
            base_dir,
            "scraping.web_crawler.seed_file",
            str(web_crawler_cfg.get("seed_file", "") or ""),
            required=True,
        )
        _check_output_path(
            report,
            base_dir,
            "scraping.web_crawler.discovery_report",
            str(web_crawler_cfg.get("discovery_report", "") or ""),
        )
        _check_output_path(
            report,
            base_dir,
            "scraping.web_crawler.audit_report_csv",
            str(web_crawler_cfg.get("audit_report_csv", "") or ""),
        )
        _check_output_path(
            report,
            base_dir,
            "scraping.web_crawler.audit_report_json",
            str(web_crawler_cfg.get("audit_report_json", "") or ""),
        )

    export_cfg = config.get("export") or {}
    if isinstance(export_cfg, dict):
        _check_output_path(report, base_dir, "export.output_dir", str(export_cfg.get("output_dir", "") or ""))
        release_cfg = export_cfg.get("release") or {}
        if isinstance(release_cfg, dict):
            _check_output_path(
                report,
                base_dir,
                "export.release.output_dir",
                str(release_cfg.get("output_dir", "") or ""),
            )

    scheduler_cfg = config.get("scheduler") or {}
    if isinstance(scheduler_cfg, dict):
        _check_output_path(report, base_dir, "scheduler.alert_file", str(scheduler_cfg.get("alert_file", "") or ""))
        state_dir = str(scheduler_cfg.get("state_dir", "") or "")
        if state_dir:
            _check_directory(report, base_dir, "scheduler.state_dir", state_dir)


def _check_placeholder_credentials(report: DoctorReport, config: dict[str, Any]) -> None:
    disabled_stage_prefixes: tuple[str, ...] = tuple(
        f"{section}.{key}."
        for section in ("scraping", "ingestion")
        for key, value in ((config.get(section) or {}).items() if isinstance(config.get(section), dict) else [])
        if isinstance(value, dict) and "enabled" in value and not value.get("enabled")
    )

    for setting, value in _iter_secret_candidates(config):
        if any(setting.startswith(prefix) for prefix in disabled_stage_prefixes):
            continue
        env_override = os.environ.get(value, "") if value else ""
        if env_override.strip():
            continue
        if _looks_like_placeholder_secret(value):
            _add_issue(
                report,
                "error",
                "placeholder-secret",
                f"Secret-like setting still uses a placeholder value: {value!r}",
                setting=setting,
                fix="Set a real secret directly in the config or export the referenced environment variable.",
            )

    scraping_cfg = config.get("scraping") or {}
    dpla_cfg = scraping_cfg.get("dpla") or {}
    if isinstance(dpla_cfg, dict) and dpla_cfg.get("enabled"):
        api_key = str(dpla_cfg.get("api_key", "") or "")
        if not api_key.strip() or (_looks_like_placeholder_secret(api_key) and not os.environ.get(api_key, "").strip()):
            _add_issue(
                report,
                "error",
                "missing-dpla-api-key",
                "DPLA scraping is enabled but no usable API key is configured.",
                setting="scraping.dpla.api_key",
                fix="Set scraping.dpla.api_key to a real key or export the placeholder environment variable before running DPLA stages.",
            )


def _require_module(
    report: DoctorReport,
    module_name: str,
    *,
    level: str,
    code: str,
    message: str,
    setting: str | None = None,
    fix: str | None = None,
) -> None:
    if not _module_available(module_name):
        _add_issue(report, level, code, message, setting=setting, fix=fix)


def _check_optional_dependencies(report: DoctorReport, config: dict[str, Any]) -> None:
    if report.validation_mode != "pydantic":
        _add_issue(
            report,
            "warning",
            "schema-validation-disabled",
            "Pydantic is not available, so structured config validation is disabled.",
            fix="Install pydantic in the active environment to enable schema validation.",
        )

    database_cfg = config.get("database") or {}
    if isinstance(database_cfg, dict) and database_cfg.get("use_mongodb", True):
        _require_module(
            report,
            "pymongo",
            level="error",
            code="missing-pymongo",
            message="MongoDB support is enabled but pymongo is not importable.",
            setting="database.use_mongodb",
            fix="Install pymongo in the active environment.",
        )
        _require_module(
            report,
            "tenacity",
            level="warning",
            code="missing-tenacity",
            message="MongoDB retry support is unavailable because tenacity is not importable.",
            fix="Install tenacity to restore retry/backoff behavior for MongoDB operations.",
        )

    scraping_cfg = config.get("scraping") or {}
    web_crawler_cfg = scraping_cfg.get("web_crawler") or {}
    if isinstance(web_crawler_cfg, dict) and web_crawler_cfg.get("enabled"):
        search_cfg = web_crawler_cfg.get("search_seeding") or {}
        if isinstance(search_cfg, dict) and search_cfg.get("enabled"):
            _require_module(
                report,
                "duckduckgo_search",
                level="warning",
                code="missing-duckduckgo-search",
                message="Web crawler search seeding is enabled but duckduckgo_search is not importable.",
                setting="scraping.web_crawler.search_seeding.enabled",
                fix="Install duckduckgo-search or disable web crawler search seeding.",
            )
        playwright_cfg = web_crawler_cfg.get("playwright_fallback") or {}
        if isinstance(playwright_cfg, dict) and playwright_cfg.get("enabled"):
            _require_module(
                report,
                "playwright",
                level="warning",
                code="missing-playwright",
                message="Web crawler Playwright fallback is enabled but playwright is not importable.",
                setting="scraping.web_crawler.playwright_fallback.enabled",
                fix="Install playwright or disable the Playwright fallback.",
            )

    culturax_cfg = scraping_cfg.get("culturax") or {}
    if isinstance(culturax_cfg, dict) and culturax_cfg.get("enabled"):
        _require_module(
            report,
            "datasets",
            level="warning",
            code="missing-datasets",
            message="CulturaX ingestion is enabled but the datasets package is not importable.",
            setting="scraping.culturax.enabled",
            fix="Install datasets or disable the CulturaX stage.",
        )

    export_cfg = config.get("export") or {}
    formats = {str(item).lower() for item in (export_cfg.get("formats") or [])}
    release_cfg = export_cfg.get("release") or {}

    needs_parquet = "parquet" in formats or bool(release_cfg) or bool(release_cfg.get("include_full_parquet", False))
    needs_huggingface = "huggingface" in formats or bool(release_cfg.get("include_huggingface", False))

    if needs_parquet:
        _require_module(
            report,
            "pandas",
            level="warning",
            code="missing-pandas",
            message="Parquet export/release artifacts require pandas, but it is not importable.",
            setting="export.formats",
            fix="Install pandas or remove parquet outputs from the export config.",
        )
        _require_module(
            report,
            "pyarrow",
            level="warning",
            code="missing-pyarrow",
            message="Parquet export/release artifacts require pyarrow, but it is not importable.",
            setting="export.formats",
            fix="Install pyarrow or remove parquet outputs from the export config.",
        )

    if needs_huggingface:
        _require_module(
            report,
            "datasets",
            level="warning",
            code="missing-huggingface-datasets",
            message="Hugging Face export/release artifacts require the datasets package, but it is not importable.",
            setting="export.formats",
            fix="Install datasets or disable Hugging Face export artifacts.",
        )


def run_doctor(
    config: dict[str, Any],
    *,
    config_path: Path | None = None,
    transition_notices: Iterable[dict[str, Any]] | None = None,
) -> DoctorReport:
    meta = config.get("_meta") or {}
    resolved_config_path = config_path or (Path(meta["config_path"]) if meta.get("config_path") else None)
    report = DoctorReport(
        config_path=str(resolved_config_path) if resolved_config_path is not None else None,
        validation_mode=str(meta.get("validation_mode", "yaml")),
    )

    base_dir = _config_base_dir(resolved_config_path)

    _check_paths(report, config, base_dir)
    _check_placeholder_credentials(report, config)
    _check_optional_dependencies(report, config)

    for notice in transition_notices or []:
        _add_issue(
            report,
            str(notice.get("level", "warning")),
            str(notice.get("code", "stage-transition")),
            str(notice.get("message", "Stage transition notice")),
            setting=notice.get("setting"),
            fix=notice.get("fix"),
            detail={key: value for key, value in notice.items() if key not in {"level", "code", "message", "setting", "fix"}},
        )

    return report


def format_doctor_report(report: DoctorReport) -> str:
    lines = [
        f"Config: {report.config_path or '<defaults-only>'}",
        f"Validation: {report.validation_mode}",
        f"Errors: {len(report.errors)}  Warnings: {len(report.warnings)}  Info: {len(report.infos)}",
    ]

    for label, issues in (("Errors", report.errors), ("Warnings", report.warnings), ("Info", report.infos)):
        if not issues:
            continue
        lines.append("")
        lines.append(f"{label}:")
        for issue in issues:
            location = f" {issue.setting}" if issue.setting else ""
            lines.append(f"- [{issue.code}]{location}: {issue.message}")
            if issue.resolved_path:
                lines.append(f"  path: {issue.resolved_path}")
            if issue.fix:
                lines.append(f"  fix: {issue.fix}")

    return "\n".join(lines)