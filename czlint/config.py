"""配置加载与校验。

配置来源优先级（后者覆盖前者）：
    1. 内置默认值 DEFAULTS
    2. 仓库根目录的 .czlintrc.json
    3. 命令行显式指定的 --config 文件

设计取舍：配置项做**白名单校验**而不是静默忽略未知键。写错一个键名
（例如把 max_subject_length 写成 maxSubjectLen）时静默忽略，会让使用者
以为自己改了规则而实际没生效，这类"静默失效"比直接报错更难排查。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping

DEFAULT_TYPES: List[str] = [
    "feat",
    "fix",
    "docs",
    "style",
    "refactor",
    "perf",
    "test",
    "build",
    "ci",
    "chore",
    "revert",
]

VALID_SEVERITIES = ("off", "warn", "error")

# 允许出现在 .czlintrc.json 顶层的键
KNOWN_KEYS = (
    "types",
    "scopes",
    "scopeRequired",
    "maxSubjectLength",
    "maxHeaderWidth",
    "maxBodyLineWidth",
    "rules",
    "ignoreSubjects",
    "strictMerges",
)

DEFAULT_RC_NAME = ".czlintrc.json"


class ConfigError(Exception):
    """配置文件不存在、不是合法 JSON，或包含非法值时抛出。"""


@dataclass
class Config:
    """一次检查使用的完整配置。字段全部有默认值，因此 Config() 即可用。"""

    types: List[str] = field(default_factory=lambda: list(DEFAULT_TYPES))
    scopes: List[str] = field(default_factory=list)
    scope_required: bool = False
    max_subject_length: int = 72
    max_header_width: int = 72
    max_body_line_width: int = 72
    rules: Dict[str, str] = field(default_factory=dict)
    ignore_subjects: List[str] = field(default_factory=list)
    strict_merges: bool = False
    source: str = "<defaults>"

    def severity(self, rule_id: str, default: str) -> str:
        """返回某条规则最终生效的严重级别（off / warn / error）。"""
        return self.rules.get(rule_id, default)


def _as_str_list(value: Any, key: str) -> List[str]:
    if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
        raise ConfigError(f"配置项 {key} 必须是字符串数组，实际是 {type(value).__name__}")
    return list(value)


def _as_pos_int(value: Any, key: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ConfigError(f"配置项 {key} 必须是正整数，实际是 {value!r}")
    return value


def _as_bool(value: Any, key: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigError(f"配置项 {key} 必须是布尔值，实际是 {value!r}")
    return value


def apply_dict(cfg: Config, data: Mapping[str, Any], known_rule_ids: List[str]) -> Config:
    """把一层配置字典叠加到 cfg 上，返回新的 Config（不修改入参）。"""
    if not isinstance(data, Mapping):
        raise ConfigError("配置文件顶层必须是一个 JSON 对象")

    unknown = [k for k in data if k not in KNOWN_KEYS]
    if unknown:
        raise ConfigError(
            "未知配置项: " + ", ".join(sorted(unknown)) + "；可用项: " + ", ".join(KNOWN_KEYS)
        )

    new = Config(
        types=list(cfg.types),
        scopes=list(cfg.scopes),
        scope_required=cfg.scope_required,
        max_subject_length=cfg.max_subject_length,
        max_header_width=cfg.max_header_width,
        max_body_line_width=cfg.max_body_line_width,
        rules=dict(cfg.rules),
        ignore_subjects=list(cfg.ignore_subjects),
        strict_merges=cfg.strict_merges,
        source=cfg.source,
    )

    if "types" in data:
        new.types = _as_str_list(data["types"], "types")
        if not new.types:
            raise ConfigError("配置项 types 不能为空数组，否则任何 type 都会被判为未知")
    if "scopes" in data:
        new.scopes = _as_str_list(data["scopes"], "scopes")
    if "scopeRequired" in data:
        new.scope_required = _as_bool(data["scopeRequired"], "scopeRequired")
    if "maxSubjectLength" in data:
        new.max_subject_length = _as_pos_int(data["maxSubjectLength"], "maxSubjectLength")
    if "maxHeaderWidth" in data:
        new.max_header_width = _as_pos_int(data["maxHeaderWidth"], "maxHeaderWidth")
    if "maxBodyLineWidth" in data:
        new.max_body_line_width = _as_pos_int(data["maxBodyLineWidth"], "maxBodyLineWidth")
    if "strictMerges" in data:
        new.strict_merges = _as_bool(data["strictMerges"], "strictMerges")
    if "ignoreSubjects" in data:
        new.ignore_subjects = _as_str_list(data["ignoreSubjects"], "ignoreSubjects")
    if "rules" in data:
        rules = data["rules"]
        if not isinstance(rules, Mapping):
            raise ConfigError("配置项 rules 必须是对象，例如 {\"R008\": \"warn\"}")
        for rid, sev in rules.items():
            if rid not in known_rule_ids:
                raise ConfigError(
                    f"未知规则 ID: {rid}；可用规则: " + ", ".join(known_rule_ids)
                )
            if sev not in VALID_SEVERITIES:
                raise ConfigError(
                    f"规则 {rid} 的严重级别必须是 {VALID_SEVERITIES} 之一，实际是 {sev!r}"
                )
        new.rules = dict(rules)

    return new


def load_file(path: str) -> Dict[str, Any]:
    if not os.path.isfile(path):
        raise ConfigError(f"配置文件不存在: {path}")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"配置文件不是合法 JSON: {path}（{exc}）") from exc


def load_config(
    repo: str = ".",
    explicit_path: str | None = None,
    known_rule_ids: List[str] | None = None,
) -> Config:
    """按优先级加载配置。explicit_path 给了就只读它，不再读仓库默认文件。"""
    ids = list(known_rule_ids or [])
    cfg = Config()

    if explicit_path:
        data = load_file(explicit_path)
        cfg = apply_dict(cfg, data, ids)
        cfg.source = explicit_path
        return cfg

    default_path = os.path.join(repo, DEFAULT_RC_NAME)
    if os.path.isfile(default_path):
        data = load_file(default_path)
        cfg = apply_dict(cfg, data, ids)
        cfg.source = default_path
    return cfg
