#!/bin/sh
set -eu
exec /Users/jingtianyu/Documents/Codex/zlibrary-search/.venv/bin/python - "$@" <<'PY'
from pathlib import Path
import shutil,sys,time
source=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path('/Users/jingtianyu/.codex/skills/zlibrary-cli')
archive=Path(sys.argv[2]).resolve() if len(sys.argv)>2 else Path('/Users/jingtianyu/.codex/skill-install-backups')
assert source.name=='zlibrary-cli' and (source/'SKILL.md').is_file()
assert source!=archive and source not in archive.parents
archive.mkdir(parents=True,exist_ok=True,mode=0o700)
target=archive/f'zlibrary-cli-{time.time_ns()}'
shutil.move(str(source),str(target))
assert not source.exists() and (target/'SKILL.md').is_file()
print('ROLLBACK PASS: skill removed from discovery; files and credentials preserved')
PY
