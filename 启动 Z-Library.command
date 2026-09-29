#!/bin/zsh
cd -- "${0:A:h}" || exit 1
./.venv/bin/python zlibrary_search.py "$@"
status_code=$?
if [[ -t 0 ]]; then
    printf '\n运行结束（退出码 %s）。按回车关闭。' "$status_code"
    read -r reply
fi
exit "$status_code"
