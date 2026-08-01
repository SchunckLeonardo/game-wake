#!/usr/bin/env bash
set -Eeuo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
terraform_dir="$project_root/terraform"
action=${1:-plan}

case "$action" in
  plan | apply) ;;
  *)
    echo "Uso: $0 [plan|apply]" >&2
    exit 64
    ;;
esac

"$project_root/scripts/package-lambda.sh"
terraform -chdir="$terraform_dir" init
terraform_files=()
while IFS= read -r terraform_file; do
  terraform_files+=("$project_root/$terraform_file")
done < <(git -C "$project_root" ls-files 'terraform/*.tf')
terraform fmt -check "${terraform_files[@]}"
terraform -chdir="$terraform_dir" validate
terraform -chdir="$terraform_dir" plan -out=tfplan
terraform -chdir="$terraform_dir" show -no-color tfplan

if [[ $action == plan ]]; then
  echo "Plano salvo em terraform/tfplan. Nenhuma alteracao foi aplicada."
  exit 0
fi

echo
echo "Revise o plano acima. Digite APLICAR para executar exatamente esse plano:"
read -r confirmation
if [[ $confirmation != APLICAR ]]; then
  echo "Apply cancelado."
  exit 1
fi

terraform -chdir="$terraform_dir" apply tfplan
