# Runbook: restore e export de World

## Restore seguro

1. Confirme permissão `ManageWorld` e step-up da ação sensível.
2. Coloque o World em `Sleeping`; não restaure sobre runtime ativo.
3. Liste backups verificados e confira game, template version, tamanho, checksum e horário.
4. Prefira “restaurar como cópia” para inspeção. O World original permanece imutável.
5. Inicie o restore uma única vez e acompanhe a Operation persistida.
6. Acorde a cópia, conecte e valide estruturas, personagens, inventário e configuração efetiva.
7. Durma a cópia com save verificado antes de qualquer promoção ou exclusão.

Nunca delete o último backup recuperável. Durante grace de armazenamento, somente backups automáticos elegíveis podem ser podados; backups manuais e a última cópia permanecem.

## Export portátil

1. Confirme permissão e step-up.
2. Gere o export sem alterar o World.
3. Baixe pelo link privado antes de expirar.
4. Verifique que o pacote contém saves nativos, configuração efetiva, versões e manifest/checksums.
5. Guarde uma cópia fora da conta AWS do GameWake.
6. Antes de encerrar uma Account, instale a versão compatível do Palworld Dedicated Server fora do GameWake, restaure o pacote e faça um login real.

Um download bem-sucedido não prova portabilidade. O gate só passa após o exercício externo abrir o mesmo progresso em um servidor independente.
