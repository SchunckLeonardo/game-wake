terraform {
  required_version = ">= 1.11.0, < 2.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "6.53.0"
    }
  }

  # Valores sao fornecidos pelo ambiente local ou GitHub Environment para que
  # nenhum nome de bucket/conta fique acoplado ao repositorio.
  backend "s3" {}
}
