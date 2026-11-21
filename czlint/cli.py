"""命令行入口。

三种用法对应三种真实场景：
 1. 回看历史：      czlint HEAD~20..HEAD
 2. commit-msg 钩子：czlint --file .git/COMMIT_EDITMSG
 3. 检查一段草稿：  czlint --stdin < msg.txt

退出码是给 CI 和钩子用的契约，不要随意改：
 0 没有 error（warn 不阻断）
 1 存在 error
 2 用法错误或配置非法
 3 读取 git 失败
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Optional

from . import __version__
from .config import ConfigError, load_config
from .gitlog import GitError, is_git_repo, read_commits, read_message_file
from .report import render_stats, render_text, summarize
from .rules import RULE_IDS, check_message, score

EXIT_OK = 0
EXIT_LINT = 1
EXIT_USAGE = 2
EXIT_GIT = 3

HOOK_TEMPLATE = """#!/bin/sh
# 由 `czlint --install-hook` 生成：提交前拦截不合规范的信息。
# 想跳过单次检查用 `git commit --no-verify`。
exec python3 -m czlint --file "$1"
"""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="czlint",
        description="零依赖的 Git 提交信息规范检查器",
    )
    p.add_argument("rev_range", nargs="?", help="git 版本范围，例如 HEAD~10..HEAD；省略则只查 HEAD")
    p.add_argument("--repo", default=".", help="仓库路径（默认当前目录）")
    p.add_argument("--config", help="显式指定配置文件，给定时不再读 .czlintrc.json")
    p.add_argument("--file", help="检查消息文件（commit-msg 钩子用）")
    p.add_argument("--stdin", action="store_true", help="从标准输入读取一条提交信息")
    p.add_argument("--all", action="store_true", help="检查全部历史提交")
    p.add_argument("-n", "--max-count", type=int, help="最多检查多少条提交")
    p.add_argument("--no-merges", action="store_true", help="跳过 merge 提交")
    p.add_argument("--json", action="store_true", help="以 JSON 输出，便于机器处理")
    p.add_argument("--stats", action="store_true", help="额外输出汇总与规则分布")
    p.add_argument("--no-hints", action="store_true", help="不输出修复建议")
    p.add_argument("--fail-on-warn", action="store_true", help="出现 warn 也返回非零")
    p.add_argument("--install-hook", action="store_true", help="在当前仓库安装 commit-msg 钩子")
    p.add_argument("--version", action="version", version="czlint " + __version__)
    return p


def lint_commits(commits, cfg) -> List[dict]:
    rows: List[dict] = []
    for commit in commits:
        issues = check_message(commit.message, cfg)
        rows.append({
            "sha": commit.short_sha,
            "subject": commit.subject,
            "issues": issues,
            "score": score(issues),
        })
    return rows


def install_hook(repo: str) -> int:
    if not is_git_repo(repo):
        print("不是 git 仓库，无法安装钩子：" + os.path.abspath(repo), file=sys.stderr)
        return EXIT_GIT
    hooks_dir = os.path.join(repo, ".git", "hooks")
    os.makedirs(hooks_dir, exist_ok=True)
    path = os.path.join(hooks_dir, "commit-msg")
    if os.path.exists(path):
        print("已存在 commit-msg 钩子，为避免覆盖别人的配置，本次不写入：" + path, file=sys.stderr)
        return EXIT_USAGE
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(HOOK_TEMPLATE)
    os.chmod(path, 0o755)
    print("已安装钩子：" + path)
    return EXIT_OK


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    if args.install_hook:
        return install_hook(args.repo)

    try:
        cfg = load_config(args.repo, args.config, RULE_IDS)
    except ConfigError as exc:
        print("配置错误：" + str(exc), file=sys.stderr)
        return EXIT_USAGE

    # 单条信息模式：钩子或草稿检查。此时 rev_range 无意义。
    if args.file or args.stdin:
        try:
            if args.file:
                message = read_message_file(args.file)
            else:
                message = sys.stdin.read()
        except GitError as exc:
            print("读取消息失败：" + str(exc), file=sys.stderr)
            return EXIT_USAGE
        issues = check_message(message, cfg)
        header = message.split("\n")[0] if message else "(空)"
        row = {"sha": "WORKTREE", "subject": header, "issues": issues, "score": score(issues)}
        rows = [row]
        source = "消息文件 " + (args.file or "<stdin>")
    else:
        rev_range = "HEAD" if args.rev_range is None and not args.all else args.rev_range
        try:
            commits = read_commits(
                repo=args.repo,
                rev_range=rev_range,
                max_count=args.max_count,
                no_merges=args.no_merges,
            )
        except GitError as exc:
            print("读取 git 失败：" + str(exc), file=sys.stderr)
            return EXIT_GIT
        rows = lint_commits(commits, cfg)
        source = "仓库 " + os.path.abspath(args.repo) + " 范围 " + (rev_range or "<全部>")

    summary = summarize(rows)
    errors = summary["errors"]
    warnings = summary["warnings"]

    if args.json:
        payload = {
            "tool": "czlint",
            "version": __version__,
            "config": cfg.source,
            "commits": [
                {
                    "sha": r["sha"],
                    "subject": r["subject"],
                    "score": r["score"],
                    "issues": [i.as_dict() for i in r["issues"]],
                }
                for r in rows
            ],
            "summary": summary,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("检查目标：" + source)
        print("当前配置：" + cfg.source)
        for line in render_text(rows, source, show_hints=not args.no_hints):
            print(line)
        if args.stats:
            for line in render_stats(summary):
                print(line)

    failed = errors > 0 or (args.fail_on_warn and warnings > 0)
    return EXIT_LINT if failed else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
