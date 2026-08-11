import type { Metadata } from "next";
import { LegalPage } from "../legal/LegalPage";

export const metadata: Metadata = {
  title: "Política de Privacidade",
  description: "Como o GameWake trata dados pessoais durante a closed beta.",
};

export default function PrivacyPage() {
  return (
    <LegalPage eyebrow="PRIVACIDADE E LGPD" title="Política de Privacidade">
      <p>Esta Política explica como o GameWake trata dados pessoais na landing page, no Console web, na Activity e nos comandos do Discord. Buscamos usar apenas os dados necessários para operar Worlds com segurança, processar pagamentos e permitir que grupos controlem seus próprios acessos.</p>

      <h2>1. Quem controla os dados</h2>
      <p>O GameWake atua como controlador dos dados descritos nesta Política. Para dúvidas ou exercício de direitos, escreva para <a href="mailto:oi@gamewake.com.br">oi@gamewake.com.br</a>.</p>

      <h2>2. Dados que tratamos</h2>
      <ul>
        <li>identificador, nome de exibição e e-mail verificado retornados pelo Discord;</li>
        <li>identificadores do servidor, canal, convite, Membership e permissões do grupo;</li>
        <li>nomes, configurações, status, operações, backups e métricas de uso dos Worlds;</li>
        <li>pacote escolhido, identificadores de checkout, estado do pagamento e lançamentos da Wallet;</li>
        <li>logs técnicos, endereço IP, informações do dispositivo e eventos de segurança necessários para prevenção de abuso e diagnóstico.</li>
      </ul>
      <p>O GameWake não recebe nem armazena dados bancários ou de cartão. O pagamento é concluído no ambiente da AbacatePay.</p>

      <h2>3. Por que usamos esses dados</h2>
      <p>Tratamos dados para autenticar usuários; criar e proteger contas e Worlds; executar comandos autorizados; mostrar custos e histórico; processar e reconciliar contribuições; prevenir fraude e abuso; atender suporte; cumprir obrigações legais; e melhorar a confiabilidade da beta.</p>

      <h2>4. Bases legais</h2>
      <p>Conforme o caso, o tratamento se apoia na execução do serviço solicitado, no cumprimento de obrigações legais ou regulatórias, no exercício regular de direitos, na prevenção à fraude e em interesses legítimos avaliados com respeito aos direitos do titular. Quando a lei exigir consentimento, ele será solicitado de forma específica.</p>

      <h2>5. Compartilhamento e operadores</h2>
      <p>Compartilhamos o mínimo necessário com o Discord para identidade, instalação e comandos; com a Amazon Web Services para computação, banco de dados, logs e armazenamento; e com a AbacatePay para checkout, confirmação e conciliação do pagamento. Também podemos compartilhar dados para cumprir ordem legal ou proteger direitos e segurança. Não vendemos dados pessoais.</p>

      <h2>6. Sessão no navegador</h2>
      <p>O Console usa o armazenamento local do navegador para manter a sessão GameWake, lembrar que você já entrou, reabrir o último grupo e World selecionados e conservar temporariamente o servidor Discord escolhido durante o onboarding. A sessão expira no servidor e pode ser removida a qualquer momento usando “Sair do GameWake” no menu do usuário ou limpando os dados do site. As preferências de último grupo e World permanecem no dispositivo para facilitar a próxima entrada. Não usamos cookies de publicidade.</p>

      <h2>7. Retenção e segurança</h2>
      <p>Mantemos dados enquanto a conta estiver ativa e pelo período necessário para segurança, suporte, conciliação financeira, cumprimento de obrigações e exercício de direitos. Depois, eliminamos ou anonimizamos os dados quando aplicável. Usamos controles de acesso, criptografia, registros imutáveis para eventos sensíveis e segregação entre identidade, pagamento e dados do World.</p>

      <h2>8. Seus direitos</h2>
      <p>Nos termos da LGPD, você pode solicitar confirmação e acesso; correção; anonimização, bloqueio ou eliminação quando cabível; portabilidade conforme regulamentação; informação sobre compartilhamentos; revisão de decisões automatizadas aplicáveis; e oposição ou revogação de consentimento quando essa for a base usada. Podemos pedir dados adicionais para confirmar sua identidade antes de atender a solicitação.</p>

      <h2>9. Atualizações e referências</h2>
      <p>Podemos atualizar esta Política conforme o produto e a legislação evoluírem. Mudanças materiais serão comunicadas de forma razoável. Consulte também o <a href="https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm" rel="noreferrer" target="_blank">texto oficial da Lei nº 13.709/2018</a> e o <a href="https://www.gov.br/anpd/pt-br" rel="noreferrer" target="_blank">portal da Autoridade Nacional de Proteção de Dados</a>.</p>
    </LegalPage>
  );
}
