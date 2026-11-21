"""输出与统计层。

把「判定结果」和「怎么显示」分开：规则层只产出 Issue 对象，这里负责
渲染成人类看的文本或机器读的 JSON。这样做的好处是加一种输出格式不用
碰规则代码，改规则也不会影响输出格式的稳定性。
"""

from __future__ import annotations

from typing import Dict, List

from .rules import RULE_TITLES


def health_bar(value: int) -> str:
    """把 0-100 的健康分画成 10 格字符条，方便终端里一眼看出好坏。"""
    filled = max(0, min(10, int(round(value / 10))))
    return "\u2588" * filled + "\u2591" * (10 - filled)


def summarize(rows: List[dict]) -> Dict:
    """汇总所有提交的问题分布，用于 --stats 与 JSON 输出。"""
    errors = sum(1 for r in rows for i in r["issues"] if i.severity == "error")
    warnings = sum(1 for r in rows for i in r["issues"] if i.severity == "warn")
    clean = sum(1 for r in rows if not r["issues"])
    by_rule: Dict[str, int] = {}
    for row in rows:
        for issue in row["issues"]:
            by_rule[issue.rule_id] = by_rule.get(issue.rule_id, 0) + 1
    avg = round(sum(r["score"] for r in rows) / len(rows), 1) if rows else 100.0
    return {
        "commits": len(rows),
        "clean_commits": clean,
        "errors": errors,
        "warnings": warnings,
        "average_score": avg,
        "by_rule": dict(sorted(by_rule.items())),
    }


def render_text(rows: List[dict], source: str, show_hints: bool = True) -> List[str]:
    """渲染逐条结果。没有问题的提交只输出一行，避免刷屏。"""
    lines: List[str] = []
    for row in rows:
        head = "{} {}".format(row["sha"], row["subject"])
        if not row["issues"]:
            lines.append("[OK  ] " + head)
            continue
        lines.append("[{:>4}] {} {}".format(row["score"], health_bar(row["score"]), head))
        for issue in row["issues"]:
            where = "  L{}".format(issue.line) if issue.line else ""
            lines.append(
                "        {sev:<5} {rid}{where}  {msg}".format(
                    sev=issue.severity.upper(),
                    rid=issue.rule_id,
                    where=where,
                    msg=issue.message,
                )
            )
            if show_hints and issue.hint:
                lines.append("              \u21b3 " + issue.hint)
    return lines


def render_stats(summary: Dict) -> List[str]:
    """渲染汇总段落：通过率 + 最常违反的规则。"""
    lines: List[str] = []
    commits = summary["commits"]
    clean = summary["clean_commits"]
    ratio = (clean / commits * 100.0) if commits else 100.0
    lines.append("")
    lines.append("汇总：{} 条提交，合规 {} 条（{:.1f}%），error {} 个，warn {} 个，平均健康分 {}".format(
        commits, clean, ratio, summary["errors"], summary["warnings"], summary["average_score"]
    ))
    if summary["by_rule"]:
        lines.append("问题分布（按规则）：")
        ranked = sorted(summary["by_rule"].items(), key=lambda kv: (-kv[1], kv[0]))
        for rid, count in ranked:
            title = RULE_TITLES.get(rid, "")
            lines.append("  {rid}  {count:>3} 处  {title}".format(rid=rid, count=count, title=title))
    else:
        lines.append("没有任何规则被触发。")
    return lines
