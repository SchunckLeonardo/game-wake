#!/usr/bin/env bash
set -Eeuo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$project_root"

python_bin=${PYTHON:-python3}
if [[ -x .venv/bin/python ]]; then
  python_bin=.venv/bin/python
fi

"$python_bin" -m pytest -q
"$python_bin" -m ruff check lambda server
"$python_bin" -m ruff format --check lambda server

bash -n scripts/*.sh server/*.sh terraform/user-data.sh.tpl
shellcheck scripts/*.sh server/*.sh

./scripts/package-lambda.sh
terraform -chdir=terraform fmt -check -recursive
if [[ ! -d terraform/.terraform ]]; then
  terraform -chdir=terraform init -backend=false
fi
terraform -chdir=terraform validate

echo "Todas as validacoes locais passaram."
