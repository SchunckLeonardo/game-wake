SHELL := /usr/bin/env bash
PYTHON ?= python3
TERRAFORM ?= terraform

.PHONY: help install-dev lambda-package test lint shellcheck fmt terraform-init terraform-validate validate clean

help:
	@printf '%s\n' \
	  'install-dev         Instala dependencias Python locais' \
	  'lambda-package      Gera build/lambda.zip para o Terraform' \
	  'test                Executa os testes Python' \
	  'lint                Executa Ruff' \
	  'shellcheck          Valida scripts Bash' \
	  'fmt                  Formata Terraform e verifica Python' \
	  'terraform-init      Inicializa providers sem backend remoto' \
	  'terraform-validate  Valida o Terraform' \
	  'validate            Executa todas as validacoes locais'

install-dev:
	$(PYTHON) -m pip install -r lambda/requirements.txt -r lambda/requirements-dev.txt

lambda-package:
	./scripts/package-lambda.sh

test:
	$(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m ruff check lambda server
	$(PYTHON) -m ruff format --check lambda server

shellcheck:
	shellcheck scripts/*.sh server/*.sh

fmt:
	$(TERRAFORM) -chdir=terraform fmt -recursive
	$(PYTHON) -m ruff format lambda server

terraform-init:
	$(TERRAFORM) -chdir=terraform init -backend=false

terraform-validate: lambda-package
	$(TERRAFORM) -chdir=terraform validate

validate:
	./scripts/validate.sh

clean:
	rm -rf build .pytest_cache .ruff_cache lambda/__pycache__ lambda/tests/__pycache__
