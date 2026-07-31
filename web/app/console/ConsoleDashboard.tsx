"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useHydrated } from "../useHydrated";

type Section =
  | "worlds"
  | "wallet"
  | "members"
  | "configuration"
  | "backups"
  | "activity";

type ConsoleDashboardProps = {
  accountId: string;
  initialSection?: Section;
  activityMode?: boolean;
};

type ConnectionDetails = {
  host: string;
  port: number;
  password?: string;
};

const sections: Array<{ id: Section; label: string; symbol: string }> = [
  { id: "worlds", label: "Worlds", symbol: "◉" },
  { id: "wallet", label: "Wallet", symbol: "◒" },
  { id: "members", label: "Membros e Roles", symbol: "♙" },
  { id: "configuration", label: "Configuração", symbol: "≡" },
  { id: "backups", label: "Backups", symbol: "↺" },
  { id: "activity", label: "Atividade", symbol: "⌁" },
];

const configurationFields = [
  {
    key: "DropItemRate",
    label: "Drop de itens dos inimigos",
    value: "3.0",
    accepted: "0.1 a 5.0",
    impact: "Multiplica a quantidade de itens derrubados por Pals e inimigos.",
  },
  {
    key: "PalEggDefaultHatchingTime",
    label: "Tempo de incubação dos ovos",
    value: "1.0",
    accepted: "0 a 240 horas",
    impact: "Define o tempo-base necessário para chocar um ovo enorme.",
  },
  {
    key: "BaseCampWorkerMaxNum",
    label: "Pals trabalhando na base",
    value: "20",
    accepted: "1 a 50",
    impact: "Limita quantos Pals podem trabalhar em cada base.",
  },
  {
    key: "MonsterFarmActionSpeedRate",
    label: "Velocidade de trabalho dos Pals",
    value: "1.5",
    accepted: "0.1 a 5.0",
    impact: "Ajusta a velocidade das ações de trabalho e produção.",
  },
];

export function ConsoleDashboard({
  accountId,
  initialSection = "worlds",
  activityMode = false,
}: ConsoleDashboardProps) {
  const hydrated = useHydrated();
  const [section, setSection] = useState<Section>(initialSection);
  const [worldStatus, setWorldStatus] = useState<"sleeping" | "waking" | "online">(
    "sleeping",
  );
  const [invites, setInvites] = useState(["Ana", "Bia"]);
  const [contribution, setContribution] = useState(25);
  const [saved, setSaved] = useState(false);
  const [connectionDetails, setConnectionDetails] =
    useState<ConnectionDetails | null>(null);

  const statusCopy = useMemo(
    () =>
      ({
        sleeping: { label: "Dormindo", detail: "R$ 0,00/h agora", icon: "☾" },
        waking: { label: "Acordando", detail: "Restaurando o World", icon: "↗" },
        online: { label: "Online", detail: "Pronto para conectar", icon: "●" },
      })[worldStatus],
    [worldStatus],
  );

  async function wakeWorld() {
    if (worldStatus !== "sleeping") return;
    setWorldStatus("waking");
    if (accountId === "demo") {
      window.setTimeout(() => setWorldStatus("online"), 900);
      return;
    }
    const response = await fetch(
      `${process.env.NEXT_PUBLIC_GAMEWAKE_API_URL ?? ""}/api/v1/accounts/${accountId}/worlds/palpagos/wake`,
      { method: "POST", credentials: "include" },
    );
    if (!response.ok) setWorldStatus("sleeping");
  }

  async function connectWorld() {
    if (accountId === "demo") {
      setConnectionDetails({
        host: "palpagos.gamewake.local",
        port: 8211,
        password: "PAL-7K2W",
      });
      return;
    }
    const response = await fetch(
      `${process.env.NEXT_PUBLIC_GAMEWAKE_API_URL ?? ""}/api/v1/accounts/${accountId}/worlds/palpagos/connection`,
      { credentials: "include" },
    );
    if (!response.ok) return;
    setConnectionDetails((await response.json()) as ConnectionDetails);
  }

  async function sleepWorld() {
    if (accountId === "demo") {
      setWorldStatus("sleeping");
      return;
    }
    const response = await fetch(
      `${process.env.NEXT_PUBLIC_GAMEWAKE_API_URL ?? ""}/api/v1/accounts/${accountId}/worlds/palpagos/sleep`,
      { method: "POST", credentials: "include" },
    );
    if (response.ok) setWorldStatus("sleeping");
  }

  function addInvite() {
    setInvites((current) =>
      current.includes("Caio") ? current : [...current, "Caio"],
    );
  }

  return (
    <main
      aria-busy={!hydrated}
      className={`console-shell${activityMode ? " activity-shell" : ""}`}
      data-discord-activity={activityMode ? "true" : undefined}
      data-hydrated={hydrated ? "true" : "false"}
      data-testid="console"
    >
      <aside className="console-sidebar">
        <Link className="brand console-brand" href="/" aria-label="GameWake — início">
          <span className="brand-mark">G</span>
          <span>GameWake</span>
        </Link>
        <div className="account-switcher">
          <span className="account-avatar">S</span>
          <div><strong>Sexta com os amigos</strong><small>Conta compartilhada</small></div>
          <span aria-hidden="true">⌄</span>
        </div>
        <nav aria-label="Áreas da Console">
          <span className="nav-caption">GERENCIAR</span>
          {sections.map((item) => (
            <button
              className={section === item.id ? "active" : ""}
              data-testid={`nav-${item.id}`}
              disabled={!hydrated}
              key={item.id}
              onClick={() => setSection(item.id)}
              type="button"
            >
              <span aria-hidden="true">{item.symbol}</span>
              {item.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-foot">
          <span className="avatar avatar-small">L</span>
          <div><strong>Leonardo</strong><small>Owner</small></div>
          <button aria-label="Configurações da conta" type="button">•••</button>
        </div>
      </aside>

      <section className="console-main">
        <header className="console-topbar">
          <div>
            <span className="mobile-brand">GW</span>
            <strong>{sections.find((item) => item.id === section)?.label}</strong>
          </div>
          <div className="topbar-actions">
            <button aria-label="Notificações" className="icon-button" type="button">♢</button>
            <span className="wallet-pill"><small>Saldo</small><strong>R$ 42,80</strong></span>
          </div>
        </header>

        <div className="console-content">
          {section === "worlds" && (
            <>
              <div className="welcome-row">
                <div>
                  <span className="section-index">VISÃO GERAL</span>
                  <h1>Bom jogo, Leonardo <span aria-hidden="true">✦</span></h1>
                  <p>Seu grupo tem um World pronto para a próxima sessão.</p>
                </div>
                <button className="button button-outline" type="button">+ Novo World</button>
              </div>

              <article className={`world-card world-${worldStatus}`}>
                <div className="world-art" aria-hidden="true">
                  <span className="world-sun" />
                  <span className="world-hill hill-one" />
                  <span className="world-hill hill-two" />
                  <span className="world-creature">P</span>
                </div>
                <div className="world-card-body">
                  <div className="world-title-row">
                    <div>
                      <span className="game-label">PALWORLD · SA-EAST-1</span>
                      <h2>Palpagos</h2>
                    </div>
                    <span className={`world-status status-${worldStatus}`}>
                      <span>{statusCopy.icon}</span>{statusCopy.label}
                    </span>
                  </div>
                  <p className="world-detail">{statusCopy.detail}</p>
                  <div className="world-stats">
                    <div><small>Última sessão</small><strong>Ontem · 2h 38min</strong></div>
                    <div><small>Último backup</small><strong>Verificado · ontem 23:42</strong></div>
                    <div><small>Custo estimado</small><strong>R$ 1,84 / hora</strong></div>
                  </div>
                  {worldStatus === "waking" && (
                    <div className="operation-progress" role="status">
                      <div><span>Restaurando World</span><strong>2 de 5</strong></div>
                      <div className="meter"><span /></div>
                      <small>Você pode sair desta tela. Avisaremos quando ficar Online.</small>
                    </div>
                  )}
                  <div className="world-actions">
                    <button
                      className="button button-primary wake-button"
                      data-testid="wake-world"
                      disabled={worldStatus !== "sleeping"}
                      onClick={wakeWorld}
                      type="button"
                    >
                      <span aria-hidden="true">↗</span>
                      {worldStatus === "sleeping" ? "Acordar World" : statusCopy.label}
                    </button>
                    {worldStatus === "online" && (
                      <>
                        <button
                          className="button button-primary"
                          data-testid="connect-world"
                          onClick={connectWorld}
                          type="button"
                        >
                          Conectar
                        </button>
                        <button
                          className="button button-quiet-dark"
                          data-testid="sleep-world"
                          onClick={sleepWorld}
                          type="button"
                        >
                          Dormir com segurança
                        </button>
                      </>
                    )}
                    <button
                      className="button button-quiet-dark"
                      onClick={() => setSection("configuration")}
                      type="button"
                    >
                      Configurar
                    </button>
                    <button className="icon-button" aria-label="Mais ações" type="button">•••</button>
                  </div>
                </div>
              </article>

              <div className="overview-grid">
                <article className="overview-card">
                  <div className="card-heading"><div><span className="card-symbol">◒</span><h3>Wallet</h3></div><button onClick={() => setSection("wallet")} type="button">Ver extrato →</button></div>
                  <strong className="overview-balance">R$ 42,80</strong>
                  <p>≈ 23 horas no perfil atual</p>
                  <div className="meter wallet-meter"><span /></div>
                  <small>Balance Guard ativo · sono seguro reservado</small>
                </article>
                <article className="overview-card">
                  <div className="card-heading"><div><span className="card-symbol">♙</span><h3>Grupo</h3></div><button onClick={() => setSection("members")} type="button">Gerenciar →</button></div>
                  <div className="member-stack" aria-label="5 membros">
                    <span>L</span><span>A</span><span>B</span><span>C</span><span>+1</span>
                  </div>
                  <strong>5 amigos com acesso</strong>
                  <p>1 Owner · 1 Manager · 3 Players</p>
                </article>
                <article className="overview-card activity-preview">
                  <div className="card-heading"><div><span className="card-symbol">⌁</span><h3>Atividade recente</h3></div><button onClick={() => setSection("activity")} type="button">Ver tudo →</button></div>
                  <ul>
                    <li><span className="event-dot green" /><div><strong>Backup verificado</strong><small>Ontem, 23:42</small></div></li>
                    <li><span className="event-dot amber" /><div><strong>World entrou em sono seguro</strong><small>Ontem, 23:41</small></div></li>
                    <li><span className="event-dot blue" /><div><strong>Ana aceitou o convite</strong><small>Segunda, 19:08</small></div></li>
                  </ul>
                </article>
              </div>
            </>
          )}

          {section === "wallet" && (
            <div className="panel-page" data-testid="wallet-panel">
              <div className="panel-heading"><div><span className="section-index">WALLET COMPARTILHADA</span><h1>Créditos do grupo</h1><p>Todo valor é explicado em um ledger imutável. A Wallet nunca fica negativa.</p></div></div>
              <div className="wallet-layout">
                <article className="balance-panel"><small>Saldo disponível</small><strong>R$ 42,80</strong><span>BRL</span><div className="guard-status"><i /> Balance Guard ativo</div></article>
                <article className="contribution-panel">
                  <h2>Adicionar créditos</h2>
                  <p>Escolha um pacote. O checkout Pix ou cartão abre de forma privada.</p>
                  <div className="amount-options" role="group" aria-label="Valor da contribuição">
                    {[25, 50, 100].map((amount) => <button className={contribution === amount ? "selected" : ""} key={amount} onClick={() => setContribution(amount)} type="button">R$ {amount}</button>)}
                  </div>
                  <button className="button button-primary full-button" data-testid="create-checkout" type="button">Contribuir R$ {contribution},00</button>
                </article>
              </div>
              <article className="table-card"><div className="card-heading"><h2>Extrato</h2><span>Julho de 2026</span></div><table><thead><tr><th>Data</th><th>Movimentação</th><th>Responsável</th><th>Valor</th></tr></thead><tbody><tr><td>30 jul, 23:41</td><td>Sessão · Palpagos</td><td>Grupo</td><td className="negative">− R$ 4,87</td></tr><tr><td>28 jul, 19:03</td><td>Contribuição</td><td>Ana</td><td className="positive">+ R$ 25,00</td></tr><tr><td>24 jul, 22:16</td><td>Crédito de disponibilidade</td><td>GameWake</td><td className="positive">+ R$ 0,42</td></tr></tbody></table></article>
            </div>
          )}

          {section === "members" && (
            <div className="panel-page" data-testid="members-panel">
              <div className="panel-heading split"><div><span className="section-index">ACESSO SIMPLES</span><h1>Membros e Roles</h1><p>Use Player, Manager e Owner. Roles personalizadas ficam em permissões avançadas.</p></div><button className="button button-primary" data-testid="invite-friends" onClick={addInvite} type="button">+ Convidar amigos</button></div>
              <article className="table-card"><div className="card-heading"><h2>Seu grupo</h2><span>{invites.length + 3} membros</span></div><div className="member-row"><span className="avatar">L</span><div><strong>Leonardo</strong><small>Você · leonardo</small></div><span className="role role-owner">Owner</span></div>{invites.map((name) => <div className="member-row" key={name}><span className="avatar pastel">{name[0]}</span><div><strong>{name}</strong><small>Discord conectado</small></div><span className="role">Player</span></div>)}<div className="member-row"><span className="avatar pastel-purple">R</span><div><strong>Rafael</strong><small>Discord conectado</small></div><span className="role role-manager">Manager</span></div></article>
              <details className="advanced-roles"><summary>Permissões avançadas e Roles personalizadas</summary><p>Crie combinações próprias e limite o acesso a Worlds específicos. As permissões são sempre aditivas.</p><button className="button button-outline" type="button">Criar Role personalizada</button></details>
            </div>
          )}

          {section === "configuration" && (
            <div className="panel-page" data-testid="configuration-panel">
              <div className="panel-heading split"><div><span className="section-index">PALWORLD · CONFIGURAÇÃO GUIADA</span><h1>Configuração</h1><p>Veja o impacto, os valores aceitos e a documentação oficial antes de alterar.</p></div><a className="button button-outline" href="https://tech.palworldgame.com/settings-and-operation/configuration/" rel="noreferrer" target="_blank">Documentação do Palworld ↗</a></div>
              <div className="config-notice"><span>i</span><p>As alterações criam uma revisão imutável e entram no próximo despertar. Se o World estiver Online, você poderá escolher uma reinicialização segura.</p></div>
              <div className="config-grid">{configurationFields.map((field) => <article className="config-card" key={field.key}><div><span className="config-key">{field.key}</span><h2>{field.label}</h2><p>{field.impact}</p></div><label>Valor<input aria-label={field.label} defaultValue={field.value} /></label><small>Valores aceitos: <strong>{field.accepted}</strong></small></article>)}</div>
              <div className="sticky-save"><div><strong>4 alterações prontas</strong><small>Será criada a revisão #12 · reinicialização necessária</small></div><button className="button button-primary" data-testid="save-configuration" onClick={() => setSaved(true)} type="button">{saved ? "Configuração salva ✓" : "Revisar e salvar"}</button></div>
            </div>
          )}

          {section === "backups" && (
            <div className="panel-page" data-testid="backups-panel">
              <div className="panel-heading split"><div><span className="section-index">RECOVERY GUARANTEE</span><h1>Backups</h1><p>A última cópia recuperável nunca é removida. Restaurar sempre cria antes um ponto de retorno.</p></div><button className="button button-primary" type="button">+ Backup manual</button></div>
              <article className="storage-card"><div><small>Armazenamento incluído</small><strong>3,8 GB de 10 GB</strong></div><div className="meter"><span /></div><p>Backups manuais e o estado atual permanecem protegidos.</p></article>
              <article className="table-card backup-list"><div className="backup-row"><span className="backup-icon">✓</span><div><strong>Backup automático</strong><small>Ontem, 23:42 · 1,2 GB · checksum verificado</small></div><span className="backup-badge">ATUAL</span><button type="button">•••</button></div><div className="backup-row"><span className="backup-icon">↺</span><div><strong>Antes da configuração #11</strong><small>28 jul, 18:57 · 1,2 GB · automático</small></div><span /><button type="button">•••</button></div><div className="backup-row"><span className="backup-icon">◆</span><div><strong>Castelo pronto</strong><small>24 jul, 22:04 · 1,1 GB · manual</small></div><span className="backup-badge manual">MANUAL</span><button type="button">•••</button></div></article>
            </div>
          )}

          {section === "activity" && (
            <div className="panel-page" data-testid="activity-panel">
              <div className="panel-heading"><div><span className="section-index">AUDITORIA REDIGIDA</span><h1>Atividade</h1><p>O grupo acompanha o que aconteceu sem expor senha, token ou dados de pagamento.</p></div></div>
              <article className="timeline-card"><div className="timeline-date">HOJE</div><div className="timeline-row"><span className="event-dot green" /><div><strong>Backup verificado</strong><p>O sono seguro do World Palpagos concluiu com uma cópia recuperável.</p><small>23:42 · GameWake</small></div></div><div className="timeline-row"><span className="event-dot amber" /><div><strong>Sessão encerrada</strong><p>Palpagos ficou online por 2h 38min. Total: R$ 4,87.</p><small>23:41 · Leonardo</small></div></div><div className="timeline-date">SEGUNDA, 28 DE JULHO</div><div className="timeline-row"><span className="event-dot blue" /><div><strong>Ana entrou no grupo</strong><p>Invitation aceito com a Role Player.</p><small>19:08 · Ana</small></div></div></article>
            </div>
          )}
        </div>

        <nav className="mobile-nav" aria-label="Navegação móvel">
          {sections.slice(0, 5).map((item) => <button className={section === item.id ? "active" : ""} data-testid={`nav-${item.id}`} disabled={!hydrated} key={item.id} onClick={() => setSection(item.id)} type="button"><span>{item.symbol}</span><small>{item.label.split(" ")[0]}</small></button>)}
        </nav>
      </section>
      {connectionDetails && (
        <div className="modal-backdrop">
          <section
            aria-label="Conectar ao Palpagos"
            aria-modal="true"
            className="connection-dialog"
            role="dialog"
          >
            <div className="dialog-heading">
              <div><span className="online-dot" /><strong>Palpagos está Online</strong></div>
              <button
                aria-label="Fechar conexão"
                onClick={() => setConnectionDetails(null)}
                type="button"
              >
                ×
              </button>
            </div>
            <h2>Entre no jogo</h2>
            <p>Estes dados são privados e nunca aparecem nos cards do grupo.</p>
            <label>
              Endereço
              <span>{connectionDetails.host}:{connectionDetails.port}</span>
            </label>
            {connectionDetails.password && (
              <label>
                Senha
                <span>{connectionDetails.password}</span>
              </label>
            )}
            <button className="button button-primary full-button" type="button">
              Copiar conexão
            </button>
          </section>
        </div>
      )}
    </main>
  );
}
