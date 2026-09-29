#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
target=${1:?Specify a copy of the modified script to restore}
[ -f "$target" ] || exit 2
[ "$(shasum -a 256 "$root/evidence/ORIGINAL.py" | cut -d ' ' -f 1)" = "1a5f0ebaf31310c10a3c714d8ea4e69df5f25ecc1cc62f226d94a7286b8ec269" ] || exit 3
backup="${target}.before-rollback.$(date +%Y%m%d%H%M%S).$$"
cp -p "$target" "$backup"
cp -p "$root/evidence/ORIGINAL.py" "$target"
cmp -s "$root/evidence/ORIGINAL.py" "$target"
printf 'ROLLBACK PASS: original bytes restored; previous file preserved\n'
