#!/usr/bin/env bash
set -Eeuo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
python_bin=${PYTHON:-python3}
build_dir="$project_root/build/lambda"
zip_file="$project_root/build/lambda.zip"
export PIP_CACHE_DIR="$project_root/build/pip-cache"

rm -rf "$build_dir" "$zip_file"
install -d "$build_dir"

"$python_bin" -m pip install \
  --disable-pip-version-check \
  --no-compile \
  --requirement "$project_root/lambda/requirements.txt" \
  --target "$build_dir" \
  --platform manylinux2014_x86_64 \
  --implementation cp \
  --python-version 3.12 \
  --only-binary=:all:

install -m 0644 "$project_root"/lambda/*.py "$build_dir"/
find "$build_dir" -type d -name '__pycache__' -prune -exec rm -rf {} +
find "$build_dir" -exec touch -t 198001010000 {} +
(
  cd "$build_dir"
  find . -type f -print | LC_ALL=C sort | zip -q -X "$zip_file" -@
)

printf 'Pacote Lambda criado: %s\n' "$zip_file"
