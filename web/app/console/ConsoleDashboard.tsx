"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { gameWakeFetch, gameWakeIdempotencyKey } from "../gamewakeApi";
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

type WorldStatus =
  | "sleeping"
  | "waking"
  | "online"
  | "going_to_sleep"
  | "needs_attention"
  | "pending_deletion";

type ApiWorld = {
  id: string;
  name: string;
  region: string;
  status: WorldStatus;
};

type ConfigurationField = {
  key: string;
  label: string;
  valueType: "string" | "integer" | "number" | "boolean";
  default: string | number | boolean;
  acceptedValues: string;
  impact: string;
  officialDocumentationUrl: string;
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
    key: "enemy_drop_item_rate",
    label: "Drop de itens dos inimigos",
    valueType: "number" as const,
    default: 3.0,
    acceptedValues: "0.1 a 5.0",
    impact: "Multiplica a quantidade de itens derrubados por Pals e inimigos.",
    officialDocumentationUrl: "https://tech.palworldgame.com/settings-and-operation/configuration/",
  },
  {
    key: "pal_egg_default_hatching_time",
    label: "Tempo de incubação dos ovos",
    valueType: "number" as const,
    default: 1.0,
    acceptedValues: "0 a 240 horas",
    impact: "Define o tempo-base necessário para chocar um ovo enorme.",
    officialDocumentationUrl: "https://tech.palworldgame.com/settings-and-operation/configuration/",
  },
  {
    key: "base_camp_worker_max_num",
    label: "Pals trabalhando na base",
    valueType: "integer" as const,
    default: 20,
    acceptedValues: "1 a 50",
    impact: "Limita quantos Pals podem trabalhar em cada base.",
    officialDocumentationUrl: "https://tech.palworldgame.com/settings-and-operation/configuration/",
  },
  {
    key: "monster_farm_action_speed_rate",
    label: "Velocidade de trabalho dos Pals",
    valueType: "number" as const,
    default: 1.5,
    acceptedValues: "0.1 a 5.0",
    impact: "Ajusta a velocidade das ações de trabalho e produção.",
    officialDocumentationUrl: "https://tech.palworldgame.com/settings-and-operation/configuration/",
  },
] satisfies ConfigurationField[];

export function ConsoleDashboard({
  accountId,
  initialSection = "worlds",
  activityMode = false,
}: ConsoleDashboardProps) {
  const hydrated = useHydrated();
  const [section, setSection] = useState<Section>(initialSection);
  const isDemo = accountId === "demo";
  const [worldStatus, setWorldStatus] = useState<WorldStatus>("sleeping");
  const [world, setWorld] = useState<ApiWorld | null>(
    isDemo ? { id: "palpagos", name: "Palpagos", region: "sa-east-1", status: "sleeping" } : null,
  );
  const [accountName, setAccountName] = useState(
    isDemo ? "Sexta com os amigos" : "Seu grupo",
  );
  const [walletBalance, setWalletBalance] = useState("42.80");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(!isDemo);
  const [invites, setInvites] = useState(["Ana", "Bia"]);
  const [contribution, setContribution] = useState(25);
  const [saved, setSaved] = useState(false);
  const [liveConfigurationFields, setLiveConfigurationFields] = useState<
    ConfigurationField[]
  >(configurationFields);
  const [configurationValues, setConfigurationValues] = useState<
    Record<string, string | number | boolean>
  >(() => Object.fromEntries(configurationFields.map((field) => [field.key, field.default])));
  const [connectionDetails, setConnectionDetails] =
    useState<ConnectionDetails | null>(null);

  const statusCopy = useMemo(
    () =>
      ({
        sleeping: { label: "Dormindo", detail: "R$ 0,00/h agora", icon: "☾" },
        waking: { label: "Acordando", detail: "Restaurando o World", icon: "↗" },
        online: { label: "Online", detail: "Pronto para conectar", icon: "●" },
        going_to_sleep: { label: "Indo dormir", detail: "Salvando e validando o World", icon: "↘" },
        needs_attention: { label: "Precisa de atenção", detail: "A operação precisa ser revisada", icon: "!" },
        pending_deletion: { label: "Exclusão pendente", detail: "Dados protegidos durante 7 dias", icon: "○" },
      })[worldStatus],
    [worldStatus],
  );
  const formattedWallet = useMemo(
    () =>
      new Intl.NumberFormat("pt-BR", {
        style: "currency",
        currency: "BRL",
      }).format(Number(walletBalance)),
    [walletBalance],
  );

  const loadLiveState = useCallback(async () => {
    if (isDemo) return;
    try {
      const [worldsResponse, walletResponse, accountsResponse] = await Promise.all([
        gameWakeFetch(`/api/v1/accounts/${accountId}/worlds`),
        gameWakeFetch(`/api/v1/accounts/${accountId}/wallet`),
        gameWakeFetch("/api/v1/me/accounts"),
      ]);
      const worldsPayload = (await worldsResponse.json()) as { worlds: ApiWorld[] };
      const walletPayload = (await walletResponse.json()) as {
        wallet: { availableBalance: string };
      };
      const accountsPayload = (await accountsResponse.json()) as {
        accounts: Array<{ id: string; name: string }>;
      };
      const selected = worldsPayload.worlds[0] ?? null;
      setWorld(selected);
      if (selected) setWorldStatus(selected.status);
      setWalletBalance(walletPayload.wallet.availableBalance);
      setAccountName(
        accountsPayload.accounts.find((account) => account.id === accountId)?.name ?? "Seu grupo",
      );
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Não foi possível carregar a Console.");
    } finally {
      setLoading(false);
    }
  }, [accountId, isDemo]);

  useEffect(() => {
    void Promise.resolve().then(loadLiveState);
  }, [loadLiveState]);

  useEffect(() => {
    if (isDemo || !["waking", "going_to_sleep"].includes(worldStatus)) return;
    const interval = window.setInterval(() => void loadLiveState(), 3000);
    return () => window.clearInterval(interval);
  }, [isDemo, loadLiveState, worldStatus]);

  useEffect(() => {
    if (isDemo || section !== "configuration" || !world) return;
    async function loadConfiguration() {
      try {
        const base = `/api/v1/accounts/${accountId}/worlds/${world.id}/configuration`;
        const [schemaResponse, revisionResponse] = await Promise.all([
          gameWakeFetch(`${base}/schema`),
          gameWakeFetch(base),
        ]);
        const schema = (await schemaResponse.json()) as {
          template: { configurationFields: ConfigurationField[] };
        };
        const revision = (await revisionResponse.json()) as {
          revision: { values: Record<string, string | number | boolean> };
        };
        setLiveConfigurationFields(schema.template.configurationFields);
        setConfigurationValues(revision.revision.values);
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "Falha ao carregar configuração.");
      }
    }
    void loadConfiguration();
  }, [accountId, isDemo, section, world]);

  async function wakeWorld() {
    if (worldStatus !== "sleeping" || !world) return;
    setWorldStatus("waking");
    if (isDemo) {
      window.setTimeout(() => setWorldStatus("online"), 900);
      return;
    }
    try {
      await gameWakeFetch(`/api/v1/accounts/${accountId}/worlds/${world.id}/wake`, {
        method: "POST",
        body: JSON.stringify({ idempotencyKey: gameWakeIdempotencyKey("wake") }),
      });
    } catch (caught) {
      setWorldStatus("sleeping");
      setError(caught instanceof Error ? caught.message : "Não foi possível acordar o World.");
    }
  }

  async function connectWorld() {
    if (!world) return;
    if (isDemo) {
      setConnectionDetails({
        host: "palpagos.gamewake.local",
        port: 8211,
        password: "PAL-7K2W",
      });
      return;
    }
    try {
      const response = await gameWakeFetch(
        `/api/v1/accounts/${accountId}/worlds/${world.id}/connection`,
      );
      const payload = (await response.json()) as { connection: ConnectionDetails };
      setConnectionDetails(payload.connection);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Não foi possível obter a conexão.");
    }
  }

  async function sleepWorld() {
    if (!world) return;
    if (isDemo) {
      setWorldStatus("sleeping");
      return;
    }
    try {
      await gameWakeFetch(`/api/v1/accounts/${accountId}/worlds/${world.id}/sleep`, {
        method: "POST",
        body: JSON.stringify({ idempotencyKey: gameWakeIdempotencyKey("sleep") }),
      });
      setWorldStatus("going_to_sleep");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Não foi possível dormir o World.");
    }
  }

  async function createCheckout() {
    if (isDemo) return;
    try {
      const response = await gameWakeFetch(
        `/api/v1/accounts/${accountId}/wallet/contributions`,
        {
          method: "POST",
          body: JSON.stringify({
            packageId: `credits-${contribution}`,
            returnUrl: window.location.href,
            completionUrl: `${window.location.href.split("?")[0]}?payment=complete`,
            idempotencyKey: gameWakeIdempotencyKey("contribution"),
          }),
        },
      );
      const payload = (await response.json()) as {
        contribution: { checkoutUrl?: string };
      };
      if (payload.contribution.checkoutUrl) {
        window.location.assign(payload.contribution.checkoutUrl);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Não foi possível abrir o checkout.");
    }
  }

  async function saveConfiguration() {
    if (isDemo) {
      setSaved(true);
      return;
    }
    if (!world) return;
    try {
      await gameWakeFetch(
        `/api/v1/accounts/${accountId}/worlds/${world.id}/configuration`,
        {
          method: "PATCH",
          body: JSON.stringify({
            changes: configurationValues,
            idempotencyKey: gameWakeIdempotencyKey("configuration"),
          }),
        },
      );
      setSaved(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Não foi possível salvar a configuração.");
    }
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
          <div><strong>{accountName}</strong><small>Conta compartilhada</small></div>
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
            <span className="wallet-pill"><small>Saldo</small><strong>{formattedWallet}</strong></span>
          </div>
        </header>

        <div className="console-content">
          {error && <div className="config-notice" role="alert"><span>!</span><p>{error}</p></div>}
          {loading && <p role="status">Carregando sua GameWake Console…</p>}
          {section === "worlds" && (
            <>
              <div className="welcome-row">
                <div>
                  <span className="section-index">VISÃO GERAL</span>
                  <h1>Bom jogo, Leonardo <span aria-hidden="true">✦</span></h1>
                  <p>{world ? "Seu grupo tem um World pronto para a próxima sessão." : "Crie o primeiro World do grupo para começar."}</p>
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
                      <span className="game-label">PALWORLD · {(world?.region ?? "sa-east-1").toUpperCase()}</span>
                      <h2>{world?.name ?? "Nenhum World"}</h2>
                    </div>
                    <span className={`world-status status-${worldStatus}`}>
                      <span>{statusCopy.icon}</span>{statusCopy.label}
                    </span>
                  </div>
                  <p className="world-detail">{statusCopy.detail}</p>
                  <div className="world-stats">
                    <div><small>Última sessão</small><strong>Ontem · 2h 38min</strong></div>
                    <div><small>Último backup</small><strong>Verificado · ontem 23:42</strong></div>
                    <div><small>Preço da sessão</small><strong>Confirmado ao acordar</strong></div>
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
                  <strong className="overview-balance">{formattedWallet}</strong>
                  <p>Saldo disponível para as próximas sessões</p>
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
                <article className="balance-panel"><small>Saldo disponível</small><strong>{formattedWallet}</strong><span>BRL</span><div className="guard-status"><i /> Balance Guard ativo</div></article>
                <article className="contribution-panel">
                  <h2>Adicionar créditos</h2>
                  <p>Escolha um pacote. O checkout Pix ou cartão abre de forma privada.</p>
                  <div className="amount-options" role="group" aria-label="Valor da contribuição">
                    {[25, 50, 100].map((amount) => <button className={contribution === amount ? "selected" : ""} key={amount} onClick={() => setContribution(amount)} type="button">R$ {amount}</button>)}
                  </div>
                  <button className="button button-primary full-button" data-testid="create-checkout" onClick={() => void createCheckout()} type="button">Contribuir R$ {contribution},00</button>
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
              <div className="config-grid">{liveConfigurationFields.map((field) => <article className="config-card" key={field.key}><div><span className="config-key">{field.key}</span><h2>{field.label}</h2><p>{field.impact}</p></div><label>Valor{field.valueType === "boolean" ? <select aria-label={field.label} onChange={(event) => setConfigurationValues((current) => ({ ...current, [field.key]: event.target.value === "true" }))} value={String(configurationValues[field.key] ?? field.default)}><option value="true">Ativado</option><option value="false">Desativado</option></select> : <input aria-label={field.label} onChange={(event) => setConfigurationValues((current) => ({ ...current, [field.key]: field.valueType === "string" ? event.target.value : Number(event.target.value) }))} type={field.valueType === "string" ? "text" : "number"} value={String(configurationValues[field.key] ?? field.default)} />}</label><small>Valores aceitos: <strong>{field.acceptedValues}</strong></small></article>)}</div>
              <div className="sticky-save"><div><strong>{liveConfigurationFields.length} opções validadas</strong><small>Uma revisão imutável será criada · reinicialização pode ser necessária</small></div><button className="button button-primary" data-testid="save-configuration" onClick={() => void saveConfiguration()} type="button">{saved ? "Configuração salva ✓" : "Revisar e salvar"}</button></div>
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
            aria-label={`Conectar ao ${world?.name ?? "World"}`}
            aria-modal="true"
            className="connection-dialog"
            role="dialog"
          >
            <div className="dialog-heading">
              <div><span className="online-dot" /><strong>{world?.name ?? "World"} está Online</strong></div>
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
