terraform {
  required_version = ">= 1.11.0, < 2.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "6.53.0"
    }
  }

  # Backend local por padrao. Para producao, migre explicitamente depois de criar
  # um bucket S3 privado e uma tabela/lockfile conforme documentado no README:
  # backend "s3" {
  #   bucket       = "SEU-BUCKET-DE-TERRAFORM"
  #   key          = "palworld-cloud-server/terraform.tfstate"
  #   region       = "us-east-1"
  #   use_lockfile = true
  #   encrypt      = true
  # }
}

