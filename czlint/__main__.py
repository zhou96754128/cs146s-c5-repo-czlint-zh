"""`python3 -m czlint` 的入口。

git 的 commit-msg 钩子模板用的是 `python3 -m czlint --file "$1"`，
所以这个文件不是可选项：没有它，装好的钩子会静默失效（退出码 1、
没有任何输出），是那种最难排查的故障。
"""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
