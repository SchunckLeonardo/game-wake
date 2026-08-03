import type { Metadata } from "next";
import { LegalPage } from "../legal/LegalPage";

export const metadata: Metadata = {
  title: "Termos de Serviço",
  description: "Termos aplicáveis à closed beta do GameWake.",
};

export default function TermsPage() {
  return (
    <LegalPage eyebrow="DOCUMENTO LEGAL" title="Termos de Serviço">
      <p>Estes Termos regulam o uso da closed beta do GameWake, uma plataforma para criar, financiar e operar Worlds de jogos com amigos pelo Console web e pelo Discord. Ao usar o serviço, você confirma que leu e aceitou estas condições.</p>

      <h2>1. Como o serviço funciona</h2>
      <p>O GameWake preserva o World e seus backups em armazenamento durável, enquanto a infraestrutura de jogo pode acordar e dormir sob demanda. Recursos, jogos e regiões disponíveis podem mudar durante a beta. Um World só fica Online depois que o processo de inicialização e a verificação de saúde terminam.</p>

      <h2>2. Conta, grupo e permissões</h2>
      <p>O acesso usa uma identidade do Discord. O Owner controla o grupo, os servidores Discord vinculados, os convites e as permissões concedidas a outras pessoas. Você deve proteger sua conta do Discord, seus códigos de recuperação e os dados privados de conexão do World. Não compartilhe acesso com quem não integra o grupo.</p>

      <h2>3. Wallet, créditos e cobrança</h2>
      <p>A Wallet é pré-paga em reais e compartilhada pelo grupo. Contribuições avulsas são processadas pela AbacatePay via Pix. Antes de acordar um World, o GameWake mostra o preço por hora e a reserva mínima da sessão. O uso efetivo, as reservas, liberações, créditos e ajustes ficam registrados no ledger da Wallet.</p>
      <p>Uma tentativa que não chega ao estado Online libera a reserva aplicável. Reembolsos de uma contribuição são integrais e dependem de todo o crédito daquela contribuição ainda estar disponível, além das regras legais e do provedor de pagamento. Disputas ou estornos podem colocar o saldo em revisão sem torná-lo negativo.</p>

      <h2>4. Worlds, backups e conteúdo</h2>
      <p>Você continua responsável pelo conteúdo e pela forma como o grupo usa o jogo. O GameWake não é afiliado aos desenvolvedores do Palworld ou ao Discord. Backups reduzem riscos, mas não substituem uma exportação feita pelo Owner quando o progresso for especialmente importante. A exclusão de um World mantém uma cópia final pelo período de proteção informado no Console antes da remoção definitiva.</p>

      <h2>5. Uso aceitável</h2>
      <p>Não use o GameWake para violar leis, direitos de terceiros, regras dos jogos ou do Discord; tentar acessar contas, Worlds ou infraestrutura sem autorização; explorar falhas; interromper o serviço; ou distribuir código malicioso. Podemos restringir operações necessárias para proteger pessoas, dados e a plataforma.</p>

      <h2>6. Closed beta e disponibilidade</h2>
      <p>A beta pode conter falhas, mudanças incompatíveis e períodos de manutenção. Não oferecemos SLA público nesta fase. Quando possível, comunicaremos incidentes e mudanças relevantes pelos canais do produto. O GameWake pode encerrar a beta ou uma conta por violação destes Termos, preservando as obrigações legais e a possibilidade de exportação aplicável.</p>

      <h2>7. Responsabilidade</h2>
      <p>Na extensão permitida pela legislação brasileira, o GameWake não responde por falhas do jogo, do Discord, do provedor de pagamento, da conexão do usuário ou por uso indevido das permissões do grupo. Nenhuma cláusula limita direitos que não possam ser afastados pelo Código de Defesa do Consumidor ou por outra norma aplicável.</p>

      <h2>8. Alterações e contato</h2>
      <p>Podemos atualizar estes Termos para refletir mudanças do produto, da lei ou da beta. A data acima identifica a versão vigente. Mudanças materiais serão comunicadas de forma razoável. Dúvidas podem ser enviadas para <a href="mailto:oi@gamewake.com.br">oi@gamewake.com.br</a>.</p>

      <h2>9. Lei aplicável</h2>
      <p>Aplicam-se as leis da República Federativa do Brasil. O foro competente será definido conforme a legislação aplicável, inclusive as regras de proteção do consumidor.</p>
    </LegalPage>
  );
}
