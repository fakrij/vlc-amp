#!/bin/bash
# make-package.sh - build the install folder for the target OS.
# Usage: tools/make-package.sh [windows|linux|all] [out dir]     (default: all, dist/)
set -euo pipefail
here=$(dirname "$0")
target=${1:-all}; out=${2:-dist}
case $target in
  windows) "$here/make-windows-package.sh" "$out" ;;
  linux)   "$here/make-linux-package.sh" "$out" ;;
  all)     "$here/make-windows-package.sh" "$out"; "$here/make-linux-package.sh" "$out" ;;
  *) echo "usage: $0 [windows|linux|all] [out dir]" >&2; exit 2 ;;
esac
