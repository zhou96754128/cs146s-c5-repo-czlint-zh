"""提交信息规则集。

设计原则：
    * 每个规则是**纯函数**（输入解析结果 + 配置，输出 Issue 列表），不读文件、
      不访问环境，因此可以脱离 git 单独测试。
    * 规则本身不带严重级别，级别由配置决定（默认值见 DEFAULT_SEVERITIES）。
      这样"同一条规则在 A 仓库是错误、在 B 仓库是提醒"不需要改代码。
    * 规则 ID 一旦发布就不复用，删规则则 ID 作废，保证 CHANGELOG 可追溯。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

from .config import Config

HEADER_RE = re.compile(
    r"^(?P<type>[A-Za-z]+)(?:\((?P<scope>[^()]*)\))?(?P<breaking>!)?: (?P<subject>.*)$"
)
BREAKING_FOOTER_RE = re.compile(r"^(?:BREAKING[ -]CHANGE):[ \t]*\S", re.MULTILINE)
MERGE_RE = re.compile(r"^Merge (?:branch|remote-tracking branch|pull request|tag)\b")
REVERT_RE = re.compile(r'^Revert "')

# 默认严重级别：会影响"这条提交能不能合入"的用 error，风格类用 warn
DEFAULT_SEVERITIES = {
    "R001": "error",   # 提交信息为空
    "R002": "error",   # 标题不符合 type(scope)!: subject
    "R003": "error",   # type 不在允许列表
    "R004": "error",   # scope 不在允许列表
    "R005": "error",   # 要求 scope 但缺失
    "R006": "error",   # subject 为空
    "R007": "error",   # subject 超长
    "R008": "off",     # subject 首字母大写（启发式，默认关闭）
    "R009": "warn",    # subject 以句号结尾
    "R010": "warn",    # 标题行过宽
    "R011": "error",   # 标题与正文之间缺少空行
    "R012": "warn",    # 正文单行过宽
    "R013": "error",   # 用了 ! 却没有 BREAKING CHANGE 脚注
    "R014": "warn",    # 行尾多余空白
    "R015": "warn",    # 正文连续空行
}

RULE_IDS = list(DEFAULT_SEVERITIES.keys())

RULE_TITLES = {
    "R001": "提交信息不能为空",
    "R002": "标题必须形如 type(scope)!: subject",
    "R003": "type 必须是允许的类型之一",
    "R004": "scope 必须是允许的范围之一",
    "R005": "本仓库要求显式 scope",
    "R006": "subject 不能为空",
    "R007": "subject 长度不得超过上限",
    "R008": "subject 首字母不应大写",
    "R009": "subject 不应以句号结尾",
    "R010": "标题行宽度不得超过上限",
    "R011": "标题与正文之间必须空一行",
    "R012": "正文单行宽度不得超过上限",
    "R013": "使用 ! 时必须在正文给出 BREAKING CHANGE 说明",
    "R014": "行尾不应有多余空白",
    "R015": "正文不应出现连续空行",
}


@dataclass
class Issue:
    rule_id: str
    severity: str
    message: str
    hint: str = ""
    line: Optional[int] = None

    def as_dict(self) -> dict:
        return {
            "rule": self.rule_id,
            "severity": self.severity,
            "line": self.line,
            "message": self.message,
            "hint": self.hint,
        }


@dataclass
class ParsedMessage:
    raw: str
    header: str
    type: Optional[str]
    scope: Optional[str]
    breaking: bool
    subject: Optional[str]
    body_lines: List[str]
    blank_after_header: bool

    @property
    def body(self) -> str:
        return "\n".join(self.body_lines)

    @property
    def is_merge(self) -> bool:
        return bool(MERGE_RE.match(self.header))

    @property
    def is_revert(self) -> bool:
        return bool(REVERT_RE.match(self.header))


def parse(message: str) -> ParsedMessage:
    """把原始提交信息切成标题与正文，并按约定格式解析标题。"""
    normalized = message.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    header = lines[0] if lines else ""

    match = HEADER_RE.match(header)
    if match:
        ctype = match.group("type")
        scope = match.group("scope")
        subject = match.group("subject")
        breaking = bool(match.group("breaking"))
    else:
        ctype = scope = subject = None
        breaking = False

    rest = lines[1:]
    blank_after_header = bool(rest) and rest[0] == ""
    body_lines = rest[1:] if blank_after_header else rest

    # 去掉末尾因 %B 带来的填充空行，避免把"信息本来就没有正文"误判成有正文
    while body_lines and body_lines[-1].strip() == "":
        body_lines.pop()

    return ParsedMessage(
        raw=normalized,
        header=header,
        type=ctype,
        scope=scope,
        breaking=breaking,
        subject=subject,
        body_lines=body_lines,
        blank_after_header=blank_after_header,
    )


def _emit(cfg: Config, issues: List[Issue], rule_id: str, message: str, hint: str = "", line=None) -> None:
    severity = cfg.severity(rule_id, DEFAULT_SEVERITIES[rule_id])
    if severity != "off":
        issues.append(Issue(rule_id, severity, message, hint, line))


def check_message(message: str, cfg: Config, strict_merges: Optional[bool] = None) -> List[Issue]:
    """对一条提交信息执行全部规则，返回按行号排序的 Issue 列表。"""
    issues: List[Issue] = []

    if not message or not message.strip():
        _emit(cfg, issues, "R001", "提交信息为空", "补一句 type: subject，例如 fix: 修复空指针")
        return issues

    parsed = parse(message)

    # 白名单：某些提交是机器生成的（如依赖升级机器人），格式注定不合约定，
    # 与其让团队反复看到同一条 error，不如按标题精确豁免。
    if parsed.header.strip() in cfg.ignore_subjects:
        return []

    # 合并提交与 revert 提交是 git 自动生成的，默认不做格式检查；
    # 若仓库显式开启 strictMerges，则照常检查（便于排查被手工改坏的合并信息）。
    strict = cfg.strict_merges if strict_merges is None else strict_merges
    if (parsed.is_merge or parsed.is_revert) and not strict:
        return _check_whitespace(cfg, parsed, issues)

    if parsed.type is None:
        _emit(
            cfg,
            issues,
            "R002",
            f"标题无法解析为 type(scope)!: subject，实际是 {parsed.header!r}",
            "示例：feat(cli): 支持 --format markdown",
            1,
        )
        return _check_whitespace(cfg, parsed, issues)

    if parsed.type not in cfg.types:
        _emit(
            cfg,
            issues,
            "R003",
            f"未知 type {parsed.type!r}",
            "允许的 type：" + ", ".join(cfg.types),
            1,
        )

    if cfg.scope_required and not parsed.scope:
        _emit(cfg, issues, "R005", "本仓库要求显式 scope，但标题里没有", "示例：fix(config): ...", 1)

    if parsed.scope and cfg.scopes and parsed.scope not in cfg.scopes:
        _emit(
            cfg,
            issues,
            "R004",
            f"未知 scope {parsed.scope!r}",
            "允许的 scope：" + ", ".join(cfg.scopes),
            1,
        )

    subject = parsed.subject or ""
    if not subject.strip():
        _emit(cfg, issues, "R006", "subject 为空", "冒号后需要一句具体描述", 1)
    else:
        if len(subject) > cfg.max_subject_length:
            _emit(
                cfg,
                issues,
                "R007",
                f"subject 长度 {len(subject)} 超过上限 {cfg.max_subject_length}",
                "把细节挪到正文，标题只留一句话",
                1,
            )
        if subject[:1].isalpha() and subject[:1].isupper():
            _emit(cfg, issues, "R008", "subject 首字母大写", "约定使用小写祈使句", 1)
        if subject.rstrip().endswith(("。", ".")):
            _emit(cfg, issues, "R009", "subject 以句号结尾", "标题不是句子，去掉结尾句号", 1)

    if len(parsed.header) > cfg.max_header_width:
        _emit(
            cfg,
            issues,
            "R010",
            f"标题行宽度 {len(parsed.header)} 超过上限 {cfg.max_header_width}",
            "缩短 type/scope 或把内容移到正文",
            1,
        )

    if parsed.body_lines and not parsed.blank_after_header:
        _emit(
            cfg,
            issues,
            "R011",
            "标题与正文之间缺少空行",
            "git 会把紧贴标题的第二行当作续行，务必空一行",
            2,
        )

    for index, line in enumerate(parsed.body_lines, start=2 if not parsed.blank_after_header else 3):
        if len(line) > cfg.max_body_line_width:
            _emit(
                cfg,
                issues,
                "R012",
                f"正文第 {index} 行宽度 {len(line)} 超过上限 {cfg.max_body_line_width}",
                "正文按 72 列换行，方便终端与邮件阅读",
                index,
            )

    if parsed.breaking and not BREAKING_FOOTER_RE.search(parsed.body):
        _emit(
            cfg,
            issues,
            "R013",
            "标题使用了 ! 但正文没有 BREAKING CHANGE 说明",
            "补一行 `BREAKING CHANGE: 具体破坏点与迁移方式`",
            1,
        )

    return _check_whitespace(cfg, parsed, issues)


def _check_whitespace(cfg: Config, parsed: ParsedMessage, issues: List[Issue]) -> List[Issue]:
    """行尾空白与连续空行：对任何提交都适用，包括合并提交。"""
    for index, line in enumerate(parsed.raw.split("\n"), start=1):
        if line != line.rstrip():
            _emit(cfg, issues, "R014", f"第 {index} 行行尾有多余空白", "编辑器可开启保存时去尾随空格", index)

    consecutive = 0
    for index, line in enumerate(parsed.raw.split("\n"), start=1):
        if line.strip() == "":
            consecutive += 1
            if consecutive >= 2:
                _emit(cfg, issues, "R015", f"第 {index} 行出现连续空行", "正文段落之间只空一行", index)
        else:
            consecutive = 0

    issues.sort(key=lambda item: (item.line or 0, item.rule_id))
    return issues


def score(issues: List[Issue]) -> int:
    """把问题折算成 0-100 的健康分：error 扣 10，warn 扣 3。"""
    errors = sum(1 for i in issues if i.severity == "error")
    warnings = sum(1 for i in issues if i.severity == "warn")
    return max(0, 100 - 10 * errors - 3 * warnings)
