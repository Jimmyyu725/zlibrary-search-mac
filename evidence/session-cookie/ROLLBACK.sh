#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
target=${1:?Specify a test copy to restore}
[ -f "$target" ] || exit 2
[ "$(shasum -a 256 "$root/BEFORE.py" | cut -d ' ' -f 1)" = "7baf48b55da74fb0860309e853035a7bea654b7d0ca924179492b96bc66a743e" ] || exit 3
cp -p "$target" "${target}.before-rollback.$(date +%Y%m%d%H%M%S).$$"
cp -p "$root/BEFORE.py" "$target"
cmp -s "$root/BEFORE.py" "$target"
printf 'ROLLBACK PASS: baseline bytes restored; modified copy preserved\n'
