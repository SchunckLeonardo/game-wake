# Runbook: recuperação do único Owner

O GameWake não tem support root com acesso permanente às Accounts. A recuperação usa identidade Discord, e-mail verificado e códigos de uso único gerados para o Owner.

## Recuperar

1. Abra a Console pela origem oficial e autentique a mesma identidade Discord.
2. O token precisa trazer um e-mail com `verified=true`; e-mail não verificado não é aceito.
3. Informe um recovery code ainda não usado pelo fluxo de recuperação.
4. O backend consome o hash atomicamente. O valor puro não é armazenado nem pode ser recuperado pelo suporte.
5. Confirme a restauração do acesso Owner e revise memberships, roles, sessões, activity e canais.
6. Gere/guarde um novo conjunto somente pelo fluxo previsto; invalide material potencialmente exposto.

## Perda total

Se identidade, e-mail verificado e todos os códigos foram perdidos, não contorne a política editando o banco ou criando um Owner oculto. Preserve a Account e abra uma análise de produto/segurança com prova auditável. A decisão deve manter a proteção contra takeover e pode exigir export/encerramento assistido no futuro.

Nunca peça recovery codes, senha de jogo, token Discord ou chave de pagamento em chat de suporte.
