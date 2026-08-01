#!/usr/bin/env bash
set -Eeuo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$project_root"

python_bin=${PYTHON:-python3}
if [[ -x .venv/bin/python ]]; then
  python_bin=.venv/bin/python
fi

"$python_bin" -m pytest -q
"$python_bin" -m ruff check gamewake lambda server scripts shared tests palworld
"$python_bin" -m ruff format --check gamewake lambda server scripts shared tests palworld

npm --prefix web run lint
npm --prefix web run test

bash -n scripts/*.sh server/*.sh terraform/user-data.sh.tpl
shellcheck scripts/*.sh server/*.sh

if rg -n 'palworld_api POST save[[:space:]]*(>|$)' server/*.sh; then
  echo "Toda chamada REST de save deve enviar um corpo JSON vazio: '{}'." >&2
  exit 1
fi

if ! rg --fixed-strings --line-regexp --quiet 'RuntimeDirectory=palworld' server/palworld.service ||
  ! rg --fixed-strings --line-regexp --quiet 'RuntimeDirectoryMode=0750' server/palworld.service; then
  echo "A unit do Palworld deve recriar /run/palworld em todo boot." >&2
  exit 1
fi

./scripts/package-lambda.sh
lambda_hash_before=$("$python_bin" -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' build/lambda.zip)
./scripts/package-lambda.sh
lambda_hash_after=$("$python_bin" -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' build/lambda.zip)
if [[ $lambda_hash_before != "$lambda_hash_after" ]]; then
  echo "O pacote Lambda nao e reprodutivel entre duas execucoes consecutivas." >&2
  exit 1
fi

terraform_files=()
while IFS= read -r terraform_file; do
  terraform_files+=("$project_root/$terraform_file")
done < <(git -C "$project_root" ls-files 'terraform/*.tf')
terraform fmt -check "${terraform_files[@]}"
if [[ ! -d terraform/.terraform ]]; then
  terraform -chdir=terraform init -backend=false
fi
terraform -chdir=terraform validate

echo "Todas as validacoes locais passaram."
