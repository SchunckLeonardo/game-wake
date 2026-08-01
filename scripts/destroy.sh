#!/usr/bin/env bash
set -Eeuo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
terraform_dir="$project_root/terraform"

terraform -chdir="$terraform_dir" init
terraform -chdir="$terraform_dir" plan -destroy -out=tfdestroy
terraform -chdir="$terraform_dir" show -no-color tfdestroy

echo
echo "ATENCAO: isso remove a EC2 e pode apagar o volume raiz."
echo "Digite DESTRUIR para executar exatamente o plano acima:"
read -r confirmation
if [[ $confirmation != DESTRUIR ]]; then
  echo "Destroy cancelado."
  exit 1
fi

terraform -chdir="$terraform_dir" apply tfdestroy

