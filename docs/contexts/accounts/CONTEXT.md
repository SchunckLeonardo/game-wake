# Accounts and Access

Este contexto define quem participa de um grupo GameWake, quem possui seus recursos e quais ações cada pessoa pode executar.

## Identity and membership

**GameWake Account**:
O perímetro de propriedade, acesso e responsabilidade financeira dos recursos de um grupo.
_Avoid_: Party, workspace, tenant, Discord server

**User**:
Uma identidade humana interna do GameWake que independe de um provedor de autenticação específico.
_Avoid_: IAM user, player, Discord user

**Linked Identity**:
Uma identidade de autenticação externa vinculada a um User.
_Avoid_: User, Membership, Discord Integration

**Game Identity**:
Uma identidade de uma rede de jogo, como Steam ou Xbox, vinculada a um User para controlar acesso nativo.
_Avoid_: Linked Identity, Discord identity, Membership

**Membership**:
O vínculo de um User com um GameWake Account, por meio do qual recebe zero ou um Role Assignment.
_Avoid_: Member, invitation, account user

**Invitation**:
Uma solicitação que precisa ser aceita antes de criar uma Membership com a Player Role.
_Avoid_: Membership, automatic enrollment, Discord membership

## Authorization

**Role**:
Um conjunto nomeado de permissões atribuído a uma Membership.
_Avoid_: profile, user type, Discord role

**Predefined Role**:
Uma Role fornecida pelo GameWake para uma responsabilidade comum.
_Avoid_: default role, system profile

**Custom Role**:
Uma Role criada em um GameWake Account para combinar permissões e limites próprios.
_Avoid_: IAM role, custom profile

**Role Assignment**:
A única atribuição ativa de Role de uma Membership dentro de um Resource Scope. Uma nova atribuição substitui a anterior.
_Avoid_: role binding, membership role

**Resource Scope**:
O GameWake Account inteiro ou o conjunto específico de recursos alcançado por um Role Assignment.
_Avoid_: permission target, resource filter

**Policy**:
O conjunto de permissões concedidas por uma Role; ausência de concessão significa negação.
_Avoid_: permission list, Discord permissions, explicit deny

## Predefined roles

**Owner**:
A Predefined Role de autoridade máxima sobre propriedade, acesso, integrações e finanças de um GameWake Account.
_Avoid_: root user, creator, super admin

**Manager**:
A Predefined Role para administrar a operação dos Worlds permitidos sem controlar propriedade, acesso ou finanças.
_Avoid_: Admin, operator

**Player**:
A Predefined Role para jogar e executar ações cotidianas seguras nos Worlds permitidos.
_Avoid_: Member, guest, basic user

## Safety

**Owner Recovery**:
O caminho emergencial para recuperar propriedade quando a Linked Identity de um Owner é perdida.
_Avoid_: everyday login, support override, Discord username proof

**Sensitive Action**:
Uma operação de alto impacto que exige reautenticação recente e confirmação explícita do recurso.
_Avoid_: routine command, Discord-only confirmation, mandatory dual approval

**Access Revocation**:
A operação que encerra autorizações do GameWake e invalida o acesso correspondente ao jogo.
_Avoid_: delayed command revocation, stale shared password, silent scheduled removal
