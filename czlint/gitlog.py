"""从 git 读取提交。

不依赖 GitPython 之类的第三方库：只用 subprocess 调系统 git，并用 ASCII 控制符
做字段/记录分隔。选 \x1f（单元分隔）与 \x1e（记录分隔）是因为它们不可能出现在
正常提交信息里，比用 "|" 或 "----" 之类的分隔符安全得多。
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from typing import List, Optional

FIELD_SEP = "\x1f"
RECORD_SEP = "\x1e"
LOG_FORMAT = "%H%x1f%an%x1f%ae%x1f%ct%x1f%s%x1f%b%x1e"


class GitError(Exception):
    """不是 git 仓库、git 未安装，或 git 命令返回非零退出码。"""


@dataclass
class Commit:
    sha: str
    author: str
    email: str
    timestamp: int
    subject: str
    body: str

    @property
    def message(self) -> str:
        """完整的提交信息（标题 + 空行 + 正文），供规则解析使用。"""
        if self.body.strip():
            return f"{self.subject}\n\n{self.body}"
        return self.subject

    @property
    def short_sha(self) -> str:
        return self.sha[:8]


def _run_git(args: List[str], cwd: str) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            ["git"] + args,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as exc:
        raise GitError("找不到 git 可执行文件，请先安装 Git") from exc


def is_git_repo(repo: str) -> bool:
    if not os.path.isdir(repo):
        return False
    proc = _run_git(["rev-parse", "--git-dir"], repo)
    return proc.returncode == 0


def read_commits(
    repo: str = ".",
    rev_range: Optional[str] = None,
    max_count: Optional[int] = None,
    no_merges: bool = False,
) -> List[Commit]:
    """按时间倒序读取提交。rev_range 例如 "HEAD~5..HEAD"。"""
    repo = os.path.abspath(repo)
    if not is_git_repo(repo):
        raise GitError(f"不是 git 仓库: {repo}")

    args = ["log", "--format=" + LOG_FORMAT]
    if no_merges:
        args.append("--no-merges")
    if max_count:
        args.extend(["-n", str(max_count)])
    if rev_range:
        args.append(rev_range)

    proc = _run_git(args, repo)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        if "does not have any commits" in detail or "unknown revision" in detail:
            raise GitError(f"无法读取提交范围 {rev_range!r}：{detail}")
        raise GitError(f"git log 失败（退出码 {proc.returncode}）：{detail}")

    commits: List[Commit] = []
    for record in proc.stdout.split(RECORD_SEP):
        record = record.strip("\n")
        if not record:
            continue
        parts = record.split(FIELD_SEP)
        if len(parts) < 6:
            continue
        sha, author, email, ts, subject, body = parts[:6]
        try:
            stamp = int(ts)
        except ValueError:
            stamp = 0
        commits.append(Commit(sha, author, email, stamp, subject, body))
    return commits


def read_message_file(path: str) -> str:
    """读取 commit-msg 钩子传入的消息文件，跳过以 # 开头的注释行。"""
    if not os.path.isfile(path):
        raise GitError(f"消息文件不存在: {path}")
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        lines = fh.read().split("\n")
    kept = [line for line in lines if not line.lstrip().startswith("#")]
    return "\n".join(kept)
