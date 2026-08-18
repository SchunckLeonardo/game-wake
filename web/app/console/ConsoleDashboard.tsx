"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { Icon, type IconName } from "../Icon";
import { DiscordSetupPanel } from "./DiscordSetupPanel";
import {
  clearGameWakeSession,
  gameWakeFetch,
  gameWakeIdempotencyKey,
  getGameWakeLastWorldId,
  setGameWakeLastAccountId,
  setGameWakeLastWorldId,
  setGameWakePostAuthReturn,
} from "../gamewakeApi";
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
  initialWorldId?: string;
  activityMode?: boolean;
};

type ConnectionDetails = {
  host: string;
  port: number;
  password?: string;
};

type WakeEstimate = {
  currency: "BRL";
  hourlyRate: string;
  minimumReservation: string;
  reservedMinutes: number;
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
  gameTemplateId?: string;
  region: string;
  status: WorldStatus;
  autoSleepMinutes?: 10 | 20 | 30 | 60 | null;
  permissions?: string[];
};

type ApiAccountAccess = {
  roles: string[];
  permissions: string[];
};

type ApiAccountSummary = {
  id: string;
  name: string;
  discordGuildId?: string | null;
  discordChannelConfigured?: boolean;
  access?: ApiAccountAccess;
  worlds: ApiWorld[];
};

const ACCOUNT_SWITCHER_CACHE_TTL_MS = 60_000;
let accountSwitcherCache: {
  expiresAt: number;
  accounts: ApiAccountSummary[];
} | null = null;
let accountSwitcherRequest: Promise<ApiAccountSummary[]> | null = null;

function cachedAccountSwitcherChoices() {
  if (!accountSwitcherCache || accountSwitcherCache.expiresAt <= Date.now()) {
    accountSwitcherCache = null;
    return null;
  }
  return accountSwitcherCache.accounts;
}

function cacheAccountSwitcherChoices(accounts: ApiAccountSummary[]) {
  accountSwitcherCache = {
    accounts,
    expiresAt: Date.now() + ACCOUNT_SWITCHER_CACHE_TTL_MS,
  };
}

function invalidateAccountSwitcherChoices() {
  accountSwitcherCache = null;
}

async function loadAccountSwitcherChoices() {
  const cached = cachedAccountSwitcherChoices();
  if (cached) return cached;
  if (accountSwitcherRequest) return accountSwitcherRequest;

  accountSwitcherRequest = (async () => {
    const response = await gameWakeFetch("/api/v1/me/accounts");
    const payload = (await response.json()) as {
      accounts: Array<Omit<ApiAccountSummary, "worlds">>;
    };
    const choices = await Promise.all(payload.accounts.map(async (account) => {
      try {
        const worldsResponse = await gameWakeFetch(`/api/v1/accounts/${account.id}/worlds`);
        const worldsPayload = (await worldsResponse.json()) as { worlds: ApiWorld[] };
        return { ...account, worlds: worldsPayload.worlds };
      } catch {
        return { ...account, worlds: [] };
      }
    }));
    cacheAccountSwitcherChoices(choices);
    return choices;
  })();

  try {
    return await accountSwitcherRequest;
  } finally {
    accountSwitcherRequest = null;
  }
}

type WorldPasswordMode = "fixed" | "random_each_run";

type WorldBudget = {
  worldId: string;
  period: string;
  monthlyLimit: string;
  spent: string;
  reserved: string;
  committed: string;
  percentage: string;
  wakeAllowed: boolean;
};

type WalletEntry = {
  id: string;
  type: string;
  amount: string;
  reference: string;
  occurredAt: string;
};

type ApiMembership = {
  id: string;
  userId: string;
  roles: Array<{ id: string; role: string; kind: "predefined" | "custom"; worldId: string | null }>;
};

type PendingMemberAction =
  | {
      kind: "remove-role";
      membershipId: string;
      roleAssignmentId: string;
      userId: string;
    }
  | {
      kind: "remove-membership";
      membershipId: string;
      userId: string;
    };

type ApiCustomRole = {
  id: string;
  name: string;
  permissions: string[];
};

type ApiBackup = {
  id: string;
  kind: "automatic" | "manual" | "restore_point" | "final";
  sizeBytes: number;
  checksumVerified: boolean;
  createdAt: string | null;
};

type ApiActivityEvent = {
  id: string;
  action: string;
  actorUserId: string;
  subjectId: string;
  occurredAt: string;
};

type ApiOperation = {
  id: string;
  type: string;
  status: string;
  phase: string;
  createdAt: string;
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

const configurationSchemaCache = new Map<string, ConfigurationField[]>();

const sections: Array<{ id: Section; label: string; icon: IconName }> = [
  { id: "worlds", label: "Worlds", icon: "globe" },
  { id: "wallet", label: "Wallet", icon: "wallet" },
  { id: "members", label: "Grupo e Discord", icon: "users" },
  { id: "configuration", label: "Configuração", icon: "settings" },
  { id: "backups", label: "Backups", icon: "database" },
  { id: "activity", label: "Atividade", icon: "activity" },
];

function isSection(value: string | null): value is Section {
  return sections.some((item) => item.id === value);
}

const legacyOwnerPermissions = [
  "world:create",
  "world:view",
  "world:wake",
  "world:sleep_when_empty",
  "world:edit",
  "world:restart",
  "world:update",
  "world:force_sleep",
  "world:logs:view",
  "backup:create",
  "backup:restore",
  "membership:manage",
  "role:manage",
  "integration:manage",
  "wallet:manage",
  "world:budget:manage",
  "world:migrate",
  "world:export",
  "world:delete",
  "account:ownership:transfer",
  "account:delete",
];

function roleLabel(role: string, customRoles: ApiCustomRole[] = []) {
  if (role === "owner") return "Owner";
  if (role === "manager") return "Moderador";
  if (role === "player") return "Player";
  return customRoles.find((custom) => custom.id === role)?.name ?? "Role personalizada";
}

const permissionLabels: Record<string, string> = {
  "world:view": "Ver Worlds",
  "world:wake": "Acordar Worlds",
  "world:sleep_when_empty": "Dormir Worlds vazios",
  "world:edit": "Editar configurações",
  "backup:create": "Criar backups",
  "backup:restore": "Restaurar backups",
  "world:logs:view": "Consultar logs",
  "world:export": "Exportar Worlds",
};

const activityLabels: Record<string, string> = {
  "membership.revoked": "Membro removido",
  "owner.recovered": "Owner recuperado",
  "role_assignment.revoked": "Role removida",
};

const backupLabels: Record<ApiBackup["kind"], string> = {
  automatic: "Backup automático",
  manual: "Backup manual",
  restore_point: "Ponto antes da restauração",
  final: "Backup final",
};

type OperationStep = {
  phase: string;
  label: string;
  detail: string;
};

const operationSteps: Record<string, OperationStep[]> = {
  wake: [
    { phase: "requested", label: "Pedido recebido", detail: "Validando o despertar e protegendo a reserva." },
    { phase: "provisioning_runtime", label: "Reservando a máquina do jogo", detail: "Separando uma máquina temporária só para este World." },
    { phase: "restoring_world", label: "Preparando a máquina do jogo", detail: "Iniciando o ambiente e restaurando seu World protegido." },
    { phase: "applying_configuration", label: "Aplicando suas configurações", detail: "Carregando as regras salvas para esta sessão." },
    { phase: "starting_game", label: "Iniciando Palworld", detail: "Abrindo o servidor do jogo com o progresso restaurado." },
    { phase: "checking_game_health", label: "Confirmando que está pronto", detail: "Testando a conexão real antes de liberar o endereço." },
    { phase: "complete", label: "World online", detail: "Tudo pronto para o grupo conectar e jogar." },
  ],
  sleep: [
    { phase: "requested", label: "Sono seguro solicitado", detail: "Organizando a proteção do progresso." },
    { phase: "checking_players", label: "Verificando jogadores", detail: "Confirmando que ninguém será desconectado sem aviso." },
    { phase: "saving_game", label: "Salvando o progresso", detail: "Pedindo ao Palworld o save mais recente." },
    { phase: "stopping_game", label: "Encerrando Palworld", detail: "Fechando o jogo depois do save." },
    { phase: "persisting_world", label: "Protegendo o World", detail: "Enviando o progresso para o armazenamento durável." },
    { phase: "creating_backup", label: "Validando o Backup", detail: "Conferindo a cópia recuperável antes de liberar a máquina." },
    { phase: "releasing_runtime", label: "Liberando a máquina", detail: "Encerrando a cobrança da infraestrutura temporária." },
    { phase: "complete", label: "World dormindo", detail: "Progresso protegido e custo de Runtime encerrado." },
  ],
  recover: [
    { phase: "requested", label: "Recuperação solicitada", detail: "Preparando uma tentativa segura." },
    { phase: "starting_game", label: "Reiniciando Palworld", detail: "Retomando o processo do jogo." },
    { phase: "checking_game_health", label: "Confirmando que está pronto", detail: "Testando a conexão real antes de liberar o endereço." },
    { phase: "complete", label: "World recuperado", detail: "Tudo pronto para conectar novamente." },
  ],
};

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatBrl(value: string | number) {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(Number(value));
}

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
  initialWorldId,
  activityMode = false,
}: ConsoleDashboardProps) {
  const hydrated = useHydrated();
  const [section, setSection] = useState<Section>(initialSection);
  const isDemo = accountId === "demo";
  const [worldStatus, setWorldStatus] = useState<WorldStatus>("sleeping");
  const [world, setWorld] = useState<ApiWorld | null>(
    isDemo ? { id: "palpagos", name: "Palpagos", region: "sa-east-1", status: "sleeping" } : null,
  );
  const [worlds, setWorlds] = useState<ApiWorld[]>(
    isDemo ? [{ id: "palpagos", name: "Palpagos", region: "sa-east-1", status: "sleeping", autoSleepMinutes: 20 }] : [],
  );
  const [showNewWorld, setShowNewWorld] = useState(false);
  const [newWorldName, setNewWorldName] = useState("");
  const [accountName, setAccountName] = useState(
    isDemo ? "Sexta com os amigos" : "Seu grupo",
  );
  const [discordGuildId, setDiscordGuildId] = useState<string | null>(
    isDemo ? "123456789012345678" : null,
  );
  const [discordChannelConfigured, setDiscordChannelConfigured] = useState(isDemo);
  const [discordCheckLoading, setDiscordCheckLoading] = useState(false);
  const [discordVerificationMessage, setDiscordVerificationMessage] = useState("");
  const [walletBalance, setWalletBalance] = useState(isDemo ? "42.80" : "0.00");
  const [walletTotalBalance, setWalletTotalBalance] = useState(isDemo ? "42.80" : "0.00");
  const [walletStatement, setWalletStatement] = useState<WalletEntry[]>([]);
  const [error, setError] = useState("");
  const [paymentNotice, setPaymentNotice] = useState("");
  const [loading, setLoading] = useState(!isDemo);
  const [invites, setInvites] = useState(["Ana", "Bia"]);
  const [inviteAccess, setInviteAccess] = useState<"play" | "console">("play");
  const [inviteRole, setInviteRole] = useState("predefined:manager");
  const [invitationLink, setInvitationLink] = useState("");
  const [invitationCopied, setInvitationCopied] = useState(false);
  const [invitationLoading, setInvitationLoading] = useState(false);
  const [memberships, setMemberships] = useState<ApiMembership[]>([]);
  const [customRoles, setCustomRoles] = useState<ApiCustomRole[]>([]);
  const [availablePermissions, setAvailablePermissions] = useState<string[]>([]);
  const [customRoleName, setCustomRoleName] = useState("");
  const [customRolePermissions, setCustomRolePermissions] = useState<string[]>([
    "world:view",
  ]);
  const [confirmationName, setConfirmationName] = useState("");
  const [roleSelections, setRoleSelections] = useState<Record<string, string>>({});
  const [pendingRoleAssignment, setPendingRoleAssignment] = useState<string | null>(null);
  const [roleActionError, setRoleActionError] = useState("");
  const [pendingMemberAction, setPendingMemberAction] = useState<PendingMemberAction | null>(null);
  const [memberActionConfirmation, setMemberActionConfirmation] = useState("");
  const [memberActionError, setMemberActionError] = useState("");
  const [memberActionLoading, setMemberActionLoading] = useState(false);
  const [customRoleConfirmation, setCustomRoleConfirmation] = useState("");
  const [customRoleError, setCustomRoleError] = useState("");
  const [customRoleLoading, setCustomRoleLoading] = useState(false);
  const [accountAccess, setAccountAccess] = useState<ApiAccountAccess>({
    roles: isDemo ? ["owner"] : [],
    permissions: isDemo ? legacyOwnerPermissions : [],
  });
  const [availableAccounts, setAvailableAccounts] = useState<ApiAccountSummary[]>([]);
  const [accountSwitcherOpen, setAccountSwitcherOpen] = useState(false);
  const [accountSwitcherLoading, setAccountSwitcherLoading] = useState(false);
  const [profileMenuOpen, setProfileMenuOpen] = useState(false);
  const [signOutConfirmation, setSignOutConfirmation] = useState(false);
  const [backups, setBackups] = useState<ApiBackup[]>([]);
  const [activityEvents, setActivityEvents] = useState<ApiActivityEvent[]>([]);
  const [worldOperations, setWorldOperations] = useState<ApiOperation[]>([]);
  const [exportUrl, setExportUrl] = useState("");
  const [deletionConfirmation, setDeletionConfirmation] = useState("");
  const [contribution, setContribution] = useState(25);
  const [checkoutLoading, setCheckoutLoading] = useState(false);
  const [saved, setSaved] = useState(false);
  const [liveConfigurationFields, setLiveConfigurationFields] = useState<
    ConfigurationField[]
  >(configurationFields);
  const [configurationValues, setConfigurationValues] = useState<
    Record<string, string | number | boolean>
  >(() => Object.fromEntries(configurationFields.map((field) => [field.key, field.default])));
  const [connectionDetails, setConnectionDetails] =
    useState<ConnectionDetails | null>(null);
  const [hasConnected, setHasConnected] = useState(isDemo);
  const [connectionCopied, setConnectionCopied] = useState(false);
  const [wakeEstimate, setWakeEstimate] = useState<WakeEstimate | null>(null);
  const [worldBudget, setWorldBudget] = useState<WorldBudget | null>(
    isDemo ? { worldId: "palpagos", period: "2026-07", monthlyLimit: "80.00", spent: "31.20", reserved: "0.00", committed: "31.20", percentage: "39.00", wakeAllowed: true } : null,
  );
  const [budgetLimit, setBudgetLimit] = useState("80.00");
  const [passwordMode, setPasswordMode] = useState<WorldPasswordMode>("fixed");
  const [savedPasswordMode, setSavedPasswordMode] = useState<WorldPasswordMode>("fixed");
  const [fixedPassword, setFixedPassword] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const liveStateRequestActive = useRef(false);
  const progressRequestKey = useRef<string | null>(null);

  useEffect(() => {
    if (!error) return;
    const timer = window.setTimeout(() => setError(""), 5_000);
    return () => window.clearTimeout(timer);
  }, [error]);

  const statusCopy = useMemo(
    () =>
      ({
        sleeping: { label: "Dormindo", detail: "R$ 0,00/h agora", icon: "moon" as IconName },
        waking: { label: "Acordando", detail: "Restaurando o World", icon: "power" as IconName },
        online: { label: "Online", detail: "Pronto para conectar", icon: "globe" as IconName },
        going_to_sleep: { label: "Indo dormir", detail: "Salvando e validando o World", icon: "shield" as IconName },
        needs_attention: { label: "Precisa de atenção", detail: "A operação precisa ser revisada", icon: "warning" as IconName },
        pending_deletion: { label: "Exclusão pendente", detail: "Dados protegidos durante 7 dias", icon: "clock" as IconName },
      })[worldStatus],
    [worldStatus],
  );
  const formattedWallet = useMemo(() => formatBrl(walletBalance), [walletBalance]);
  const reservedWalletAmount = useMemo(
    () => Math.max(0, Number(walletTotalBalance) - Number(walletBalance)),
    [walletBalance, walletTotalBalance],
  );
  const formattedReservedWallet = useMemo(
    () => formatBrl(reservedWalletAmount),
    [reservedWalletAmount],
  );
  const activeOperation = useMemo(
    () => [...worldOperations].reverse().find((operation) => ["pending", "running"].includes(operation.status)) ?? null,
    [worldOperations],
  );
  const operationProgress = useMemo(() => {
    if (!activeOperation) return null;
    const steps = operationSteps[activeOperation.type] ?? [{
      phase: activeOperation.phase,
      label: activeOperation.phase.replaceAll("_", " "),
      detail: "Acompanhando a etapa atual da operação.",
    }];
    const foundIndex = steps.findIndex((step) => step.phase === activeOperation.phase);
    const index = Math.max(0, foundIndex);
    return {
      current: index + 1,
      total: steps.length,
      label: steps[index]?.label ?? activeOperation.phase.replaceAll("_", " "),
      detail: steps[index]?.detail ?? "Acompanhando a etapa atual da operação.",
      steps: steps.map((step, stepIndex) => ({
        ...step,
        state: stepIndex < index ? "complete" : stepIndex === index ? "current" : "pending",
      })),
      startedAt: new Date(activeOperation.createdAt).toLocaleTimeString("pt-BR", {
        hour: "2-digit",
        minute: "2-digit",
      }),
    };
  }, [activeOperation]);
  const latestOperation = useMemo(
    () => [...worldOperations].reverse()[0] ?? null,
    [worldOperations],
  );
  const effectivePermissions = useMemo(
    () => new Set(world?.permissions ?? accountAccess.permissions),
    [accountAccess.permissions, world?.permissions],
  );
  const can = useCallback(
    (permission: string) => isDemo || effectivePermissions.has(permission),
    [effectivePermissions, isDemo],
  );
  const visibleSections = useMemo(
    () => sections.filter((item) => {
      if (item.id === "worlds") return can("world:view");
      if (item.id === "members") {
        return can("membership:manage") || can("role:manage") || can("integration:manage");
      }
      if (item.id === "configuration") return can("world:edit");
      if (item.id === "backups") {
        return can("backup:create") || can("backup:restore") || can("world:export");
      }
      return true;
    }),
    [can],
  );
  const activeSection = visibleSections.some((item) => item.id === section)
    ? section
    : (visibleSections[0]?.id ?? "worlds");
  const viewerRole = useMemo(() => {
    if (accountAccess.roles.includes("owner")) return "Owner";
    if (accountAccess.roles.includes("manager")) return "Moderador";
    if (accountAccess.roles.includes("player")) return "Player";
    return accountAccess.roles.length > 0 ? "Role personalizada" : "Acesso carregando";
  }, [accountAccess.roles]);
  const selectedWorldId = world?.id;

  const updateConsoleUrl = useCallback(
    (nextSection: Section, nextWorldId: string | undefined, mode: "push" | "replace") => {
      const parameters = new URLSearchParams(window.location.search);
      parameters.set("section", nextSection);
      if (nextWorldId) parameters.set("world", nextWorldId);
      else parameters.delete("world");
      const query = parameters.toString();
      window.history[mode === "push" ? "pushState" : "replaceState"](
        null,
        "",
        `/accounts/${encodeURIComponent(accountId)}${query ? `?${query}` : ""}`,
      );
    },
    [accountId],
  );

  const navigateToSection = useCallback(
    (nextSection: Section) => {
      setSection(nextSection);
      setError("");
      updateConsoleUrl(nextSection, selectedWorldId, "push");
    },
    [selectedWorldId, updateConsoleUrl],
  );

  useEffect(() => {
    if (isDemo) return;
    const rememberReauthenticationReturn = (event: MouseEvent) => {
      const target = event.target instanceof Element ? event.target : null;
      const link = target?.closest<HTMLAnchorElement>(
        'a[href^="/auth/discord/start?"][href*="accountId="]',
      );
      if (link) {
        setGameWakePostAuthReturn(`${window.location.pathname}${window.location.search}`);
      }
    };
    document.addEventListener("click", rememberReauthenticationReturn, { capture: true });
    return () => document.removeEventListener("click", rememberReauthenticationReturn, { capture: true });
  }, [isDemo]);

  const loadLiveState = useCallback(async () => {
    if (isDemo) return;
    try {
      const [worldsResult, walletResult, accountsResult] = await Promise.allSettled([
        gameWakeFetch(`/api/v1/accounts/${accountId}/worlds`).then(async (response) =>
          (await response.json()) as { worlds: ApiWorld[] },
        ),
        gameWakeFetch(`/api/v1/accounts/${accountId}/wallet`).then(async (response) =>
          (await response.json()) as {
            wallet: { balance?: string; availableBalance: string; statement: WalletEntry[] };
          },
        ),
        gameWakeFetch("/api/v1/me/accounts").then(async (response) =>
          (await response.json()) as {
            accounts: Array<{
              id: string;
              name: string;
              discordGuildId?: string | null;
              discordChannelConfigured?: boolean;
              access?: ApiAccountAccess;
            }>;
          },
        ),
      ]);

      if (worldsResult.status === "rejected") throw worldsResult.reason;
      const worldsPayload = worldsResult.value;
      setWorlds(worldsPayload.worlds);
      setWorld((current) => {
        const rememberedWorldId = getGameWakeLastWorldId(accountId);
        const selected = worldsPayload.worlds.find((item) => item.id === current?.id)
          ?? worldsPayload.worlds.find((item) => item.id === initialWorldId)
          ?? worldsPayload.worlds.find((item) => item.id === rememberedWorldId)
          ?? worldsPayload.worlds[0]
          ?? null;
        if (selected) setWorldStatus(selected.status);
        return selected;
      });

      if (walletResult.status === "fulfilled") {
        const wallet = walletResult.value.wallet;
        setWalletBalance(wallet.availableBalance);
        setWalletTotalBalance(wallet.balance ?? wallet.availableBalance);
        setWalletStatement(wallet.statement ?? []);
      }
      if (accountsResult.status === "fulfilled") {
        const account = accountsResult.value.accounts.find((item) => item.id === accountId);
        setAccountName(account?.name ?? "Seu grupo");
        setDiscordGuildId(account?.discordGuildId ?? null);
        setDiscordChannelConfigured(account?.discordChannelConfigured ?? false);
        setAccountAccess(
          account?.access ?? { roles: [], permissions: [] },
        );
      }
      const partialFailures = [walletResult, accountsResult].filter(
        (result) => result.status === "rejected",
      ).length;
      setError(
        partialFailures > 0
          ? "O progresso do World está atualizado. Alguns dados auxiliares serão recarregados automaticamente."
          : "",
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Não foi possível carregar a Console.");
    } finally {
      setLoading(false);
    }
  }, [accountId, initialWorldId, isDemo]);

  const loadWorldState = useCallback(async () => {
    if (isDemo || liveStateRequestActive.current || document.hidden) return;
    liveStateRequestActive.current = true;
    try {
      const response = await gameWakeFetch(`/api/v1/accounts/${accountId}/worlds`);
      const payload = (await response.json()) as { worlds: ApiWorld[] };
      setWorlds(payload.worlds);
      setWorld((current) => {
        const selected = payload.worlds.find((item) => item.id === current?.id)
          ?? payload.worlds.find((item) => item.id === initialWorldId)
          ?? payload.worlds.find((item) => item.id === getGameWakeLastWorldId(accountId))
          ?? payload.worlds[0]
          ?? null;
        if (selected) setWorldStatus(selected.status);
        return selected;
      });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Não foi possível atualizar o World.");
    } finally {
      liveStateRequestActive.current = false;
    }
  }, [accountId, initialWorldId, isDemo]);

  useEffect(() => {
    void Promise.resolve().then(loadLiveState);
  }, [loadLiveState]);

  useEffect(() => {
    if (isDemo || !world) return;
    setGameWakeLastAccountId(accountId);
    setGameWakeLastWorldId(accountId, world.id);
  }, [accountId, isDemo, world]);

  useEffect(() => {
    function restoreUrlState() {
      const parameters = new URLSearchParams(window.location.search);
      const restoredSection = parameters.get("section");
      if (isSection(restoredSection)) setSection(restoredSection);
      const restoredWorldId = parameters.get("world");
      const restoredWorld = worlds.find((item) => item.id === restoredWorldId);
      if (!restoredWorld) return;
      setWorld(restoredWorld);
      setWorldStatus(restoredWorld.status);
      setWorldOperations([]);
      setBackups([]);
      setConnectionDetails(null);
      setExportUrl("");
    }
    window.addEventListener("popstate", restoreUrlState);
    return () => window.removeEventListener("popstate", restoreUrlState);
  }, [worlds]);

  useEffect(() => {
    if (!accountSwitcherOpen && !profileMenuOpen) return;
    function closeMenus(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      setAccountSwitcherOpen(false);
      setProfileMenuOpen(false);
      setSignOutConfirmation(false);
    }
    window.addEventListener("keydown", closeMenus);
    return () => window.removeEventListener("keydown", closeMenus);
  }, [accountSwitcherOpen, profileMenuOpen]);

  useEffect(() => {
    let active = true;
    void Promise.resolve().then(() => {
      if (!active) return;
      setHasConnected(
        isDemo ||
          (world !== null &&
            window.localStorage.getItem(
              `gamewake:first-session-complete:${accountId}:${world.id}`,
            ) === "1"),
      );
    });
    return () => {
      active = false;
    };
  }, [accountId, isDemo, world]);

  useEffect(() => {
    if (isDemo) return;
    const parameters = new URLSearchParams(window.location.search);
    if (parameters.get("payment") !== "complete") return;
    const storageKey = `gamewake:pending-contribution:${accountId}`;
    const contributionId =
      parameters.get("contributionId") ?? window.localStorage.getItem(storageKey);

    let active = true;
    let retryTimer: number | undefined;
    async function reconcile(attempt: number) {
      try {
        const response = await gameWakeFetch(
          `/api/v1/accounts/${accountId}/wallet/contributions/${contributionId}/reconcile`,
          { method: "POST" },
        );
        const payload = (await response.json()) as {
          contribution: { status: string };
        };
        if (!active) return;
        if (payload.contribution.status === "completed") {
          await loadLiveState();
          if (!active) return;
          setPaymentNotice("Pagamento confirmado. Seus créditos já estão disponíveis.");
          window.localStorage.removeItem(storageKey);
          parameters.delete("payment");
          parameters.delete("contributionId");
          parameters.set("section", "wallet");
          if (selectedWorldId) parameters.set("world", selectedWorldId);
          const query = parameters.toString();
          window.history.replaceState(
            null,
            "",
            `${window.location.pathname}${query ? `?${query}` : ""}`,
          );
          return;
        }
        if (attempt < 4) {
          retryTimer = window.setTimeout(() => void reconcile(attempt + 1), 1500);
          return;
        }
        setPaymentNotice(
          "Pagamento em confirmação. Seus créditos aparecerão automaticamente na Wallet.",
        );
      } catch (caught) {
        if (!active) return;
        setError(
          caught instanceof Error
            ? caught.message
            : "Não foi possível confirmar o pagamento agora.",
        );
      }
    }
    async function handlePaymentReturn() {
      await Promise.resolve();
      if (!active) return;
      setSection("wallet");
      updateConsoleUrl("wallet", selectedWorldId, "replace");
      if (!contributionId) {
        setPaymentNotice(
          "Pagamento recebido. Atualize a Wallet em alguns instantes para confirmar o saldo.",
        );
        await loadLiveState();
        return;
      }
      await reconcile(0);
    }
    void handlePaymentReturn();
    return () => {
      active = false;
      if (retryTimer !== undefined) window.clearTimeout(retryTimer);
    };
  }, [accountId, isDemo, loadLiveState, selectedWorldId, updateConsoleUrl]);

  useEffect(() => {
    if (isDemo || !["waking", "going_to_sleep"].includes(worldStatus)) return;
    const refreshVisibleWorld = () => {
      if (!document.hidden) void loadWorldState();
    };
    const interval = window.setInterval(refreshVisibleWorld, 3000);
    document.addEventListener("visibilitychange", refreshVisibleWorld);
    return () => {
      window.clearInterval(interval);
      document.removeEventListener("visibilitychange", refreshVisibleWorld);
    };
  }, [isDemo, loadWorldState, worldStatus]);

  useEffect(() => {
    if (isDemo || !selectedWorldId) return;
    let active = true;
    async function loadProgress() {
      if (progressRequestKey.current === selectedWorldId || document.hidden) return;
      progressRequestKey.current = selectedWorldId;
      try {
        const response = await gameWakeFetch(
          `/api/v1/accounts/${accountId}/worlds/${selectedWorldId}/operations`,
        );
        const payload = (await response.json()) as { operations: ApiOperation[] };
        if (active) setWorldOperations(payload.operations);
      } catch {
        // Status polling remains best-effort; the persisted World status is authoritative.
      } finally {
        if (progressRequestKey.current === selectedWorldId) progressRequestKey.current = null;
      }
    }
    void loadProgress();
    const isTransitioning = ["waking", "going_to_sleep"].includes(worldStatus);
    const interval = isTransitioning ? window.setInterval(() => void loadProgress(), 3000) : undefined;
    const refreshVisibleProgress = () => {
      if (isTransitioning && !document.hidden) void loadProgress();
    };
    document.addEventListener("visibilitychange", refreshVisibleProgress);
    return () => {
      active = false;
      if (interval !== undefined) window.clearInterval(interval);
      document.removeEventListener("visibilitychange", refreshVisibleProgress);
    };
  }, [accountId, isDemo, selectedWorldId, worldStatus]);

  useEffect(() => {
    if (isDemo || activeSection !== "wallet" || !world) return;
    async function loadBudget() {
      try {
        const response = await gameWakeFetch(
          `/api/v1/accounts/${accountId}/worlds/${world?.id}/budget`,
        );
        const payload = (await response.json()) as { budget: WorldBudget | null };
        setWorldBudget(payload.budget);
        if (payload.budget) setBudgetLimit(payload.budget.monthlyLimit);
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "Não foi possível carregar o orçamento.");
      }
    }
    void loadBudget();
  }, [accountId, activeSection, isDemo, world]);

  useEffect(() => {
    if (isDemo || activeSection !== "configuration" || !world) return;
    async function loadConfiguration() {
      try {
        const base = `/api/v1/accounts/${accountId}/worlds/${world.id}/configuration`;
        const schemaCacheKey = world.gameTemplateId;
        const cachedSchema = schemaCacheKey
          ? configurationSchemaCache.get(schemaCacheKey)
          : undefined;
        const schemaFields = cachedSchema
          ? Promise.resolve(cachedSchema)
          : gameWakeFetch(`${base}/schema`).then(async (response) => {
              const schema = (await response.json()) as {
                template: { id?: string; configurationFields: ConfigurationField[] };
              };
              const key = schema.template.id ?? schemaCacheKey;
              if (key) configurationSchemaCache.set(key, schema.template.configurationFields);
              return schema.template.configurationFields;
            });
        const [fields, revisionResponse, passwordResponse] = await Promise.all([
          schemaFields,
          gameWakeFetch(base),
          gameWakeFetch(`/api/v1/accounts/${accountId}/worlds/${world.id}/access/password`),
        ]);
        const revision = (await revisionResponse.json()) as {
          revision: { values: Record<string, string | number | boolean> };
        };
        const password = (await passwordResponse.json()) as {
          password: { mode: WorldPasswordMode };
        };
        setLiveConfigurationFields(fields);
        setConfigurationValues(revision.revision.values);
        setPasswordMode(password.password.mode);
        setSavedPasswordMode(password.password.mode);
        setFixedPassword("");
        setPasswordError("");
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "Falha ao carregar configuração.");
      }
    }
    void loadConfiguration();
  }, [accountId, activeSection, isDemo, world]);

  useEffect(() => {
    if (isDemo) return;
    async function loadSection() {
      try {
        if (activeSection === "members") {
          const [membersResponse, rolesResponse] = await Promise.all([
            gameWakeFetch(`/api/v1/accounts/${accountId}/memberships`),
            gameWakeFetch(`/api/v1/accounts/${accountId}/roles`),
          ]);
          const members = (await membersResponse.json()) as { memberships: ApiMembership[] };
          const roles = (await rolesResponse.json()) as {
            customRoles: ApiCustomRole[];
            permissions: string[];
          };
          setMemberships(members.memberships);
          setCustomRoles(roles.customRoles);
          setAvailablePermissions(roles.permissions);
        }
        if (activeSection === "backups" && world) {
          const response = await gameWakeFetch(
            `/api/v1/accounts/${accountId}/worlds/${world.id}/backups`,
          );
          const payload = (await response.json()) as { backups: ApiBackup[] };
          setBackups(payload.backups);
        }
        if (activeSection === "activity") {
          const [activityResponse, operationsResponse] = await Promise.all([
            gameWakeFetch(`/api/v1/accounts/${accountId}/activity`),
            world
              ? gameWakeFetch(
                  `/api/v1/accounts/${accountId}/worlds/${world.id}/operations`,
                )
              : Promise.resolve(null),
          ]);
          const activity = (await activityResponse.json()) as { events: ApiActivityEvent[] };
          setActivityEvents(activity.events);
          if (operationsResponse) {
            const operations = (await operationsResponse.json()) as {
              operations: ApiOperation[];
            };
            setWorldOperations(operations.operations);
          }
        }
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "Não foi possível carregar esta área.");
      }
    }
    void loadSection();
  }, [accountId, activeSection, isDemo, world]);

  async function wakeWorld() {
    if (!world) {
      setError("Crie seu primeiro World antes de tentar acordá-lo.");
      setShowNewWorld(true);
      return;
    }
    if (!["sleeping", "needs_attention"].includes(worldStatus)) return;
    if (isDemo) {
      setWakeEstimate({
        currency: "BRL",
        hourlyRate: "2.49",
        minimumReservation: "1.04",
        reservedMinutes: 25,
      });
      return;
    }
    try {
      const response = await gameWakeFetch(
        `/api/v1/accounts/${accountId}/worlds/${world.id}/wake/estimate`,
      );
      const payload = (await response.json()) as { estimate: WakeEstimate };
      setWakeEstimate(payload.estimate);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Não foi possível calcular o preço.");
    }
  }

  async function confirmWake() {
    if (!world || !wakeEstimate) return;
    setWakeEstimate(null);
    setWorldStatus("waking");
    setWorld((current) => current ? { ...current, status: "waking" } : current);
    if (isDemo) {
      const operation: ApiOperation = {
        id: "demo-wake",
        type: "wake",
        status: "running",
        phase: "restoring_world",
        createdAt: new Date().toISOString(),
      };
      setWorldOperations([operation]);
      window.setTimeout(() => {
        setWorldStatus("online");
        setWorldOperations([{ ...operation, status: "succeeded", phase: "complete" }]);
      }, 900);
      return;
    }
    try {
      const response = await gameWakeFetch(`/api/v1/accounts/${accountId}/worlds/${world.id}/wake`, {
        method: "POST",
        body: JSON.stringify({ idempotencyKey: gameWakeIdempotencyKey("wake") }),
      });
      const payload = (await response.json()) as { operation: ApiOperation };
      setWorldOperations((current) => [...current, payload.operation]);
    } catch (caught) {
      setWorldStatus(world.status);
      setWorld((current) => current ? { ...current, status: world.status } : current);
      setError(caught instanceof Error ? caught.message : "Não foi possível acordar o World.");
    }
  }

  async function createWorld() {
    if (!newWorldName.trim()) return;
    if (isDemo) {
      const created = {
        id: crypto.randomUUID(),
        name: newWorldName.trim(),
        region: "sa-east-1",
        status: "sleeping" as const,
        autoSleepMinutes: 20 as const,
      };
      setWorld(created);
      setWorlds((current) => [...current, created]);
      setWorldStatus(created.status);
      setShowNewWorld(false);
      setNewWorldName("");
      return;
    }
    try {
      setError("");
      const response = await gameWakeFetch(`/api/v1/accounts/${accountId}/worlds`, {
        method: "POST",
        body: JSON.stringify({
          name: newWorldName.trim(),
          gameTemplateId: "palworld:1",
          region: "sa-east-1",
          runtimeProfileId: "palworld-small",
          idempotencyKey: gameWakeIdempotencyKey("create-world"),
        }),
      });
      const payload = (await response.json()) as { world: ApiWorld };
      setWorld(payload.world);
      setWorlds((current) => [...current.filter((item) => item.id !== payload.world.id), payload.world]);
      setWorldStatus(payload.world.status);
      invalidateAccountSwitcherChoices();
      setShowNewWorld(false);
      setNewWorldName("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Não foi possível criar o World.");
    }
  }

  async function updateAutoSleep(value: string) {
    if (!world) return;
    const autoSleepMinutes = value === "off" ? null : Number(value) as 10 | 20 | 30 | 60;
    if (isDemo) {
      const updated = { ...world, autoSleepMinutes };
      setWorld(updated);
      setWorlds((current) => current.map((item) => item.id === updated.id ? updated : item));
      return;
    }
    try {
      const response = await gameWakeFetch(
        `/api/v1/accounts/${accountId}/worlds/${world.id}/settings`,
        {
          method: "PATCH",
          body: JSON.stringify({ autoSleepMinutes }),
        },
      );
      const payload = (await response.json()) as { world: ApiWorld };
      setWorld(payload.world);
      setWorlds((current) => current.map((item) => item.id === payload.world.id ? payload.world : item));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Não foi possível alterar o Auto Sleep.");
    }
  }

  async function saveWorldBudget() {
    if (!world || !budgetLimit) return;
    if (isDemo) {
      setWorldBudget((current) => current ? { ...current, monthlyLimit: budgetLimit } : null);
      setSaved(true);
      return;
    }
    try {
      const response = await gameWakeFetch(
        `/api/v1/accounts/${accountId}/worlds/${world.id}/budget`,
        {
          method: "PUT",
          body: JSON.stringify({
            monthlyLimit: budgetLimit,
            idempotencyKey: gameWakeIdempotencyKey("world-budget"),
          }),
        },
      );
      const payload = (await response.json()) as { budget: WorldBudget };
      setWorldBudget(payload.budget);
      setSaved(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Não foi possível salvar o orçamento.");
    }
  }

  async function connectWorld() {
    if (!world) return;
    setConnectionCopied(false);
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
      window.localStorage.setItem(
        `gamewake:first-session-complete:${accountId}:${world.id}`,
        "1",
      );
      setHasConnected(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Não foi possível obter a conexão.");
    }
  }

  async function copyConnection() {
    if (!connectionDetails) return;
    const value = `${connectionDetails.host}:${connectionDetails.port}${connectionDetails.password ? `\n${connectionDetails.password}` : ""}`;
    await navigator.clipboard.writeText(value);
    setConnectionCopied(true);
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
    if (isDemo || checkoutLoading) return;
    setCheckoutLoading(true);
    setError("");
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
        contribution: { id: string; checkoutUrl?: string };
      };
      if (payload.contribution.checkoutUrl) {
        window.localStorage.setItem(
          `gamewake:pending-contribution:${accountId}`,
          payload.contribution.id,
        );
        window.location.assign(payload.contribution.checkoutUrl);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Não foi possível abrir o checkout.");
    } finally {
      setCheckoutLoading(false);
    }
  }

  async function openAccountSwitcher() {
    setAccountSwitcherOpen(true);
    setProfileMenuOpen(false);
    if (isDemo) {
      setAvailableAccounts([{
        id: "demo",
        name: accountName,
        discordGuildId,
        access: accountAccess,
        worlds,
      }]);
      return;
    }
    const cached = cachedAccountSwitcherChoices();
    if (cached) {
      setAvailableAccounts(cached);
      setAccountSwitcherLoading(false);
      return;
    }
    setAccountSwitcherLoading(true);
    setAvailableAccounts([]);
    try {
      const choices = await loadAccountSwitcherChoices();
      setAvailableAccounts(choices);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Não foi possível listar seus grupos.");
    } finally {
      setAccountSwitcherLoading(false);
    }
  }

  async function refreshDiscordIntegration() {
    if (isDemo) {
      setDiscordChannelConfigured(true);
      setDiscordVerificationMessage("Conexão confirmada. Os comandos estão prontos.");
      return;
    }
    setDiscordCheckLoading(true);
    setDiscordVerificationMessage("");
    try {
      const response = await gameWakeFetch("/api/v1/me/accounts");
      const payload = (await response.json()) as {
        accounts: Array<{
          id: string;
          discordGuildId?: string | null;
          discordChannelConfigured?: boolean;
        }>;
      };
      const account = payload.accounts.find((item) => item.id === accountId);
      const nextGuildId = account?.discordGuildId ?? null;
      const nextChannelConfigured = account?.discordChannelConfigured ?? false;
      setDiscordGuildId(nextGuildId);
      setDiscordChannelConfigured(nextChannelConfigured);
      setDiscordVerificationMessage(
        nextChannelConfigured
          ? "Conexão confirmada. Os comandos estão prontos."
          : "Ainda não recebemos /gamewake comecar. Execute o comando no Discord e tente novamente.",
      );
    } catch (caught) {
      setDiscordVerificationMessage(
        caught instanceof Error
          ? caught.message
          : "Não foi possível verificar agora. Tente novamente.",
      );
    } finally {
      setDiscordCheckLoading(false);
    }
  }

  function selectWorld(item: ApiWorld) {
    setWorld(item);
    setWorldStatus(item.status);
    setWorldOperations([]);
    setBackups([]);
    setConnectionDetails(null);
    setExportUrl("");
    setSaved(false);
    if (!isDemo) {
      setGameWakeLastAccountId(accountId);
      setGameWakeLastWorldId(accountId, item.id);
    }
    updateConsoleUrl(activeSection, item.id, "push");
  }

  function signOut() {
    invalidateAccountSwitcherChoices();
    clearGameWakeSession();
    window.location.assign("/");
  }

  async function saveConfiguration() {
    setPasswordError("");
    const passwordChanged = passwordMode !== savedPasswordMode || fixedPassword.length > 0;
    if (passwordMode === "fixed" && passwordChanged && fixedPassword.length < 6) {
      setPasswordError("Escolha uma senha com pelo menos 6 caracteres.");
      return;
    }
    if (isDemo) {
      setSavedPasswordMode(passwordMode);
      setFixedPassword("");
      setSaved(true);
      return;
    }
    if (!world) return;
    try {
      const requests: Promise<Response>[] = [
        gameWakeFetch(
          `/api/v1/accounts/${accountId}/worlds/${world.id}/configuration`,
          {
            method: "PATCH",
            body: JSON.stringify({
              changes: configurationValues,
              idempotencyKey: gameWakeIdempotencyKey("configuration"),
            }),
          },
        ),
      ];
      if (passwordChanged) {
        requests.push(gameWakeFetch(
          `/api/v1/accounts/${accountId}/worlds/${world.id}/access/password`,
          {
            method: "PATCH",
            body: JSON.stringify({
              mode: passwordMode,
              ...(passwordMode === "fixed" ? { password: fixedPassword } : {}),
            }),
          },
        ));
      }
      await Promise.all(requests);
      setSavedPasswordMode(passwordMode);
      setFixedPassword("");
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

  async function createInvitationLink() {
    if (invitationLoading) return;
    if (isDemo) {
      addInvite();
      setInvitationLink(
        `${window.location.origin}/convites/demo/${crypto.randomUUID()}`,
      );
      return;
    }
    const [kind, roleId] = inviteRole.split(":", 2);
    setInvitationLoading(true);
    setInvitationCopied(false);
    setError("");
    try {
      const response = await gameWakeFetch(
        `/api/v1/accounts/${accountId}/invitation-links`,
        {
        method: "POST",
          body: JSON.stringify({
            access: inviteAccess,
            ...(inviteAccess === "console" && kind === "custom"
              ? { customRoleId: roleId }
              : inviteAccess === "console"
                ? { predefinedRole: roleId }
                : {}),
          }),
        },
      );
      const payload = (await response.json()) as { invitation: { id: string } };
      setInvitationLink(
        `${window.location.origin}/convites/${accountId}/${payload.invitation.id}`,
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Não foi possível criar o link.");
    } finally {
      setInvitationLoading(false);
    }
  }

  async function copyInvitationLink() {
    if (!invitationLink) return;
    await navigator.clipboard.writeText(invitationLink);
    setInvitationCopied(true);
  }

  async function createCustomRole() {
    if (isDemo || !customRoleName.trim() || customRolePermissions.length === 0) return;
    if (customRoleConfirmation !== accountName) {
      setCustomRoleError(`Digite exatamente “${accountName}” para confirmar.`);
      return;
    }
    if (customRoleLoading) return;
    setCustomRoleLoading(true);
    setCustomRoleError("");
    try {
      const response = await gameWakeFetch(`/api/v1/accounts/${accountId}/roles`, {
        method: "POST",
        body: JSON.stringify({
          name: customRoleName.trim(),
          permissions: customRolePermissions,
          confirmedResourceName: customRoleConfirmation,
        }),
      });
      const payload = (await response.json()) as { role: ApiCustomRole };
      setCustomRoles((current) => [...current, payload.role]);
      setCustomRoleName("");
      setCustomRoleConfirmation("");
    } catch (caught) {
      setCustomRoleError(
        caught instanceof Error ? caught.message : "Não foi possível criar a Role.",
      );
    } finally {
      setCustomRoleLoading(false);
    }
  }

  async function assignRole(membershipId: string) {
    const selected = roleSelections[membershipId];
    if (isDemo || !selected) return;
    if (confirmationName !== accountName) {
      setRoleActionError(`Digite exatamente “${accountName}” para confirmar.`);
      return;
    }
    const [kind, roleId] = selected.split(":", 2);
    setRoleActionError("");
    try {
      const response = await gameWakeFetch(
        `/api/v1/accounts/${accountId}/memberships/${membershipId}/roles`,
        {
          method: "POST",
          body: JSON.stringify({
            ...(kind === "custom" ? { customRoleId: roleId } : { predefinedRole: roleId }),
            confirmedResourceName: confirmationName,
          }),
        },
      );
      const payload = (await response.json()) as { membership: ApiMembership };
      setMemberships((current) => current.map((item) => item.id === membershipId ? payload.membership : item));
      setRoleSelections((current) => ({ ...current, [membershipId]: "" }));
      setPendingRoleAssignment(null);
      setConfirmationName("");
    } catch (caught) {
      setRoleActionError(
        caught instanceof Error ? caught.message : "Não foi possível atribuir a Role.",
      );
    }
  }

  function beginRoleAssignment(membershipId: string) {
    if (!roleSelections[membershipId]) return;
    setPendingMemberAction(null);
    setPendingRoleAssignment(membershipId);
    setConfirmationName("");
    setRoleActionError("");
  }

  async function removeRole(
    membershipId: string,
    roleAssignmentId: string,
    confirmedResourceName: string,
  ) {
    if (isDemo) return;
    try {
      const response = await gameWakeFetch(
        `/api/v1/accounts/${accountId}/memberships/${membershipId}/roles/${roleAssignmentId}`,
        {
          method: "DELETE",
          body: JSON.stringify({ confirmedResourceName }),
        },
      );
      const payload = (await response.json()) as { membership: ApiMembership };
      setMemberships((current) => current.map((item) => item.id === membershipId ? payload.membership : item));
    } catch (caught) {
      throw caught instanceof Error ? caught : new Error("Não foi possível remover a Role.");
    }
  }

  async function removeMembership(membershipId: string, confirmedResourceName: string) {
    if (isDemo) return;
    try {
      await gameWakeFetch(
        `/api/v1/accounts/${accountId}/memberships/${membershipId}`,
        {
          method: "DELETE",
          body: JSON.stringify({ confirmedResourceName }),
        },
      );
      setMemberships((current) => current.filter((item) => item.id !== membershipId));
    } catch (caught) {
      throw caught instanceof Error ? caught : new Error("Não foi possível remover o membro.");
    }
  }

  function beginMemberAction(action: PendingMemberAction) {
    setPendingRoleAssignment(null);
    setPendingMemberAction(action);
    setMemberActionConfirmation("");
    setMemberActionError("");
  }

  async function confirmMemberAction() {
    if (!pendingMemberAction || memberActionLoading) return;
    if (memberActionConfirmation !== accountName) {
      setMemberActionError(`Digite exatamente “${accountName}” para confirmar.`);
      return;
    }
    setMemberActionLoading(true);
    setMemberActionError("");
    try {
      if (pendingMemberAction.kind === "remove-role") {
        await removeRole(
          pendingMemberAction.membershipId,
          pendingMemberAction.roleAssignmentId,
          memberActionConfirmation,
        );
      } else {
        await removeMembership(
          pendingMemberAction.membershipId,
          memberActionConfirmation,
        );
      }
      setPendingMemberAction(null);
      setMemberActionConfirmation("");
    } catch (caught) {
      setMemberActionError(
        caught instanceof Error ? caught.message : "Não foi possível concluir a remoção.",
      );
    } finally {
      setMemberActionLoading(false);
    }
  }

  async function createManualBackup() {
    if (isDemo || !world) return;
    try {
      const response = await gameWakeFetch(
        `/api/v1/accounts/${accountId}/worlds/${world.id}/backups`,
        {
          method: "POST",
          body: JSON.stringify({ idempotencyKey: gameWakeIdempotencyKey("backup") }),
        },
      );
      const payload = (await response.json()) as { backup: ApiBackup };
      setBackups((current) => [...current, payload.backup]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Não foi possível criar o Backup.");
    }
  }

  async function restoreBackup(backupId: string) {
    if (isDemo || !world) return;
    try {
      await gameWakeFetch(
        `/api/v1/accounts/${accountId}/worlds/${world.id}/backups/${backupId}/restore`,
        {
          method: "POST",
          body: JSON.stringify({ idempotencyKey: gameWakeIdempotencyKey("restore") }),
        },
      );
      setSaved(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Não foi possível restaurar o Backup.");
    }
  }

  async function exportWorld() {
    if (isDemo || !world) return;
    try {
      const response = await gameWakeFetch(
        `/api/v1/accounts/${accountId}/worlds/${world.id}/exports`,
        {
          method: "POST",
          body: JSON.stringify({ idempotencyKey: gameWakeIdempotencyKey("export") }),
        },
      );
      const payload = (await response.json()) as { export: { downloadUrl: string } };
      setExportUrl(payload.export.downloadUrl);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Não foi possível exportar o World.");
    }
  }

  async function scheduleWorldDeletion() {
    if (isDemo || !world || deletionConfirmation !== world.name) return;
    try {
      const response = await gameWakeFetch(
        `/api/v1/accounts/${accountId}/worlds/${world.id}`,
        {
          method: "DELETE",
          body: JSON.stringify({
            confirmedResourceName: deletionConfirmation,
            idempotencyKey: gameWakeIdempotencyKey("delete-world"),
          }),
        },
      );
      const payload = (await response.json()) as { world: ApiWorld };
      setWorld(payload.world);
      setWorldStatus(payload.world.status);
      setDeletionConfirmation("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Não foi possível agendar a exclusão.");
    }
  }

  async function cancelWorldDeletion() {
    if (isDemo || !world) return;
    try {
      const response = await gameWakeFetch(
        `/api/v1/accounts/${accountId}/worlds/${world.id}/deletion/cancel`,
        { method: "POST" },
      );
      const payload = (await response.json()) as { world: ApiWorld };
      setWorld(payload.world);
      setWorldStatus(payload.world.status);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Não foi possível cancelar a exclusão.");
    }
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
          <span className="brand-mark"><Icon name="power" size={19} /></span>
          <span>GameWake</span>
        </Link>
        <button
          aria-expanded={accountSwitcherOpen}
          aria-label="Trocar grupo ou servidor"
          className="account-switcher"
          disabled={!hydrated}
          onClick={() => void openAccountSwitcher()}
          type="button"
        >
          <span className="account-avatar">{accountName[0]?.toUpperCase() ?? "G"}</span>
          <div><strong>{accountName}</strong><small>{worlds.length} World{worlds.length === 1 ? "" : "s"} · trocar grupo</small></div>
          <Icon name="chevron-down" size={16} />
        </button>
        <nav aria-label="Áreas da Console">
          <span className="nav-caption">GERENCIAR</span>
          {visibleSections.map((item) => (
            <button
              className={activeSection === item.id ? "active" : ""}
              data-testid={`nav-${item.id}`}
              disabled={!hydrated}
              key={item.id}
              onClick={() => navigateToSection(item.id)}
              type="button"
            >
              <span aria-hidden="true"><Icon name={item.icon} size={18} /></span>
              {item.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-legal">
          <Link href="/terms">Termos</Link>
          <Link href="/privacy">Privacidade</Link>
        </div>
        <button
          aria-expanded={profileMenuOpen}
          aria-label="Abrir menu do usuário"
          className="sidebar-foot"
          disabled={!hydrated}
          onClick={() => { setProfileMenuOpen((current) => !current); setSignOutConfirmation(false); }}
          type="button"
        >
          <span className="avatar avatar-small">{isDemo ? "L" : "V"}</span>
          <div><strong>{isDemo ? "Leonardo" : "Você"}</strong><small>{viewerRole}</small></div>
          <Icon name="chevron-down" size={16} />
        </button>
      </aside>

      <section className="console-main">
        <header className="console-topbar">
          <div>
            <span className="mobile-brand"><Icon name="power" size={17} /></span>
            <span className="topbar-section-title"><strong>{visibleSections.find((item) => item.id === activeSection)?.label}</strong><small>Seu acesso: {viewerRole}</small></span>
          </div>
          <div className="topbar-actions">
            {!isDemo && (
              <button
                aria-expanded={accountSwitcherOpen}
                aria-label="Trocar grupo ou servidor"
                className="discord-switch-link"
                disabled={!hydrated}
                onClick={() => void openAccountSwitcher()}
                type="button"
              >
                <Icon name="discord" size={17} /><span>Trocar grupo</span>
              </button>
            )}
            <button aria-label="Notificações" className="icon-button" type="button"><Icon name="bell" size={18} /></button>
            <button
              aria-expanded={profileMenuOpen}
              aria-label="Abrir menu do usuário"
              className="icon-button mobile-profile-button"
              disabled={!hydrated}
              onClick={() => { setProfileMenuOpen((current) => !current); setSignOutConfirmation(false); }}
              type="button"
            ><span className="avatar avatar-small">{isDemo ? "L" : "V"}</span></button>
            <span className="wallet-pill"><small>Saldo</small><strong>{formattedWallet}</strong></span>
          </div>
        </header>

        <div className="console-content">
          {error && <div className="config-notice" role="alert"><span><Icon name="warning" size={15} /></span><p>{error}</p></div>}
          {paymentNotice && <div className="payment-notice" role="status"><span><Icon name="check" size={15} /></span><p>{paymentNotice}</p></div>}
          {loading && <p role="status">Carregando sua GameWake Console…</p>}
          {activeSection === "worlds" && (
            <>
              <div className="welcome-row">
                <div>
                  {isDemo && <span className="console-demo-label">Dados demonstrativos</span>}
                  <h1>{isDemo ? "Bom jogo, Leonardo" : "Bom jogo, seu grupo"}</h1>
                  <p>{world ? "Seu grupo tem um World pronto para a próxima sessão." : "Crie o primeiro World do grupo para começar."}</p>
                </div>
                {can("world:create") && <button aria-label="+ Novo World" className="button button-outline" disabled={!hydrated} onClick={() => setShowNewWorld((current) => !current)} type="button"><Icon name="plus" size={17} />Novo World</button>}
              </div>

              {can("integration:manage") && !discordChannelConfigured && (
                <article className="discord-setup-nudge">
                  <span><Icon name="discord" size={19} /></span>
                  <div>
                    <strong>{discordGuildId ? "O GameWake está instalado, mas falta ativar um canal" : "Use /gamewake sem configurar nada à mão"}</strong>
                    <p>{discordGuildId ? "O Owner executa /gamewake comecar uma vez no canal onde o grupo joga." : "Escolha o servidor Discord e a GameWake cuida dos comandos para você."}</p>
                  </div>
                  <button className="button button-outline" onClick={() => navigateToSection("members")} type="button">Configurar Discord</button>
                </article>
              )}

              {showNewWorld && <article className="contribution-panel"><h2>Criar World</h2><p>Palworld em São Paulo, com preço confirmado antes de cada sessão.</p><div className="inline-action-form"><label>Nome do novo World<input aria-label="Nome do novo World" autoFocus onChange={(event) => setNewWorldName(event.target.value)} placeholder="Ex.: Palpagos" value={newWorldName} /></label><button className="button button-primary" disabled={!newWorldName.trim()} onClick={() => void createWorld()} type="button">Criar World</button></div></article>}

              {!world && !showNewWorld && (
                <section className="empty-world-state" data-testid="empty-world-state">
                  <span className="empty-world-icon"><Icon name="globe" size={28} /></span>
                  <span className="section-index">PRÓXIMO PASSO</span>
                  <h2>Seu grupo ainda não tem um World</h2>
                  <p>Crie o World antes de tentar acordá-lo. Ele só existe depois que você escolhe um nome e confirma esta etapa.</p>
                  <ol className="first-run-path">
                    <li className="done"><Icon name="check" size={16} /><span><strong>Conta do grupo pronta</strong><small>{discordGuildId ? "Servidor Discord conectado" : "Você pode conectar um servidor agora ou depois"}</small></span></li>
                    <li className="current"><span>2</span><span><strong>Criar o primeiro World</strong><small>Leva menos de um minuto e ainda não gera custo de runtime</small></span></li>
                    <li><span>3</span><span><strong>Adicionar créditos via Pix</strong><small>O grupo escolhe R$ 25, R$ 50 ou R$ 100</small></span></li>
                    <li><span>4</span><span><strong>Acordar e jogar</strong><small>Você verá o preço antes de confirmar</small></span></li>
                  </ol>
                  <div className="empty-world-actions">
                    <button className="button button-primary" disabled={!hydrated} onClick={() => setShowNewWorld(true)} type="button"><Icon name="plus" size={17} />Criar meu primeiro World</button>
                    {!discordGuildId && <Link className="button button-outline" href={`/auth/discord/start?accountId=${encodeURIComponent(accountId)}`}><Icon name="discord" size={17} />Conectar Discord</Link>}
                  </div>
                  <div className="discord-command-guide"><Icon name="discord" size={19} /><p><strong>Prefere começar no Discord?</strong> {discordChannelConfigured ? <>Use <code>/gamewake comecar</code> somente se quiser trocar o canal do grupo. Depois do convite, cada amigo usa <code>/gamewake aceitar</code>.</> : <>Abra <button onClick={() => navigateToSection("members")} type="button">Grupo e Discord</button> e siga os dois passos guiados.</>}</p></div>
                </section>
              )}

              {world && !isDemo && !hasConnected && (
                <article className="first-session-guide" data-testid="first-session-guide">
                  <div className="first-session-heading">
                    <span><Icon name="power" size={20} /></span>
                    <div><span className="section-index">PRIMEIRA PARTIDA</span><h2>Falta pouco para jogar</h2><p>Siga estes passos uma vez. A GameWake cuida do servidor e do save para o grupo.</p></div>
                  </div>
                  <ol className="first-session-steps">
                    <li className="done"><Icon name="check" size={15} /><span><strong>World criado</strong><small>{world.name} está salvo e não gera custo enquanto dorme.</small></span></li>
                    <li className={Number(walletBalance) > 0 ? "done" : "current"}>{Number(walletBalance) > 0 ? <Icon name="check" size={15} /> : <span>2</span>}<span><strong>Adicionar créditos</strong><small>{Number(walletBalance) > 0 ? `${formattedWallet} disponíveis para o grupo.` : "Escolha R$ 25, R$ 50 ou R$ 100 e pague por Pix."}</small></span></li>
                    <li className={worldStatus === "online" ? "done" : Number(walletBalance) > 0 ? "current" : "pending"}>{worldStatus === "online" ? <Icon name="check" size={15} /> : <span>3</span>}<span><strong>Acordar o World</strong><small>{worldStatus === "waking" ? "A GameWake está preparando a partida agora." : worldStatus === "online" ? "O servidor está online e pronto." : worldStatus === "needs_attention" ? "A tentativa anterior foi encerrada com segurança. Você pode tentar novamente." : "Você confere o preço antes de confirmar."}</small></span></li>
                    <li className={worldStatus === "online" ? "current" : "pending"}><span>4</span><span><strong>Conectar e jogar</strong><small>Abra o endereço e a senha quando o World estiver online.</small></span></li>
                  </ol>
                  <div className="first-session-routes">
                    <section className="first-session-route" aria-labelledby="console-first-session">
                      <div className="first-session-route-heading">
                        <span><Icon name="globe" size={17} /></span>
                        <div><h3 id="console-first-session">Pelo Console</h3><p>Faça tudo nesta tela, com preço e progresso visíveis.</p></div>
                      </div>
                      <div className="first-session-action">
                        {Number(walletBalance) <= 0 && <button className="button button-primary" onClick={() => navigateToSection("wallet")} type="button"><Icon name="wallet" size={17} />Adicionar créditos</button>}
                        {Number(walletBalance) > 0 && can("world:wake") && ["sleeping", "needs_attention"].includes(worldStatus) && <button className="button button-primary" onClick={() => void wakeWorld()} type="button"><Icon name="power" size={17} />{worldStatus === "needs_attention" ? "Tentar novamente" : "Acordar o World"}</button>}
                        {worldStatus === "online" && <button className="button button-primary" onClick={() => void connectWorld()} type="button"><Icon name="globe" size={17} />Ver como conectar</button>}
                        {["waking", "going_to_sleep"].includes(worldStatus) && <span><Icon name="clock" size={16} /> Pode sair desta tela; a operação continua protegida.</span>}
                      </div>
                    </section>
                    <section className="first-session-route discord-first-session" aria-labelledby="discord-first-session">
                      <div className="first-session-route-heading">
                        <span><Icon name="discord" size={17} /></span>
                        <div><h3 id="discord-first-session">Pelo Discord</h3><p>Use o mesmo World no servidor Discord conectado.</p></div>
                      </div>
                      {discordChannelConfigured ? <>
                        <ol className="discord-first-session-steps">
                          <li><code>/gamewake acordar</code><span>inicia a partida</span></li>
                          <li><code>/gamewake status</code><span>acompanha o preparo</span></li>
                          <li><code>/gamewake conectar</code><span>entrega IP e senha em privado</span></li>
                        </ol>
                        <p className="discord-friend-flow">Para chamar o grupo: <code>/gamewake convidar @amigo1 @amigo2</code>. Cada amigo entra usando <code>/gamewake aceitar</code>.</p>
                      </> : <div className="discord-route-blocked"><strong>Antes, ative o Discord do grupo</strong><p>Você verá exatamente onde instalar e qual único comando executar.</p><button className="button button-outline" onClick={() => navigateToSection("members")} type="button">Configurar Discord</button></div>}
                    </section>
                  </div>
                </article>
              )}

              {worlds.length > 1 && (
                <div className="world-selector" role="tablist" aria-label="Selecionar World">
                  {worlds.map((item) => (
                    <button
                      aria-selected={item.id === world?.id}
                      className={item.id === world?.id ? "selected" : ""}
                      key={item.id}
                      onClick={() => selectWorld(item)}
                      role="tab"
                      type="button"
                    >
                      {item.name}<small>{item.status.replaceAll("_", " ")}</small>
                    </button>
                  ))}
                </div>
              )}

              {world && <section className={`console-world-stage world-${worldStatus}`}>
                <div className="console-status-band">
                  <div>
                    <span className={`status-band-icon status-${worldStatus}`}><Icon name={statusCopy.icon} size={19} /></span>
                    <span><small>World selecionado</small><strong>{world ? "Conexão protegida" : "Nenhum World"}</strong></span>
                    <span className={`world-status status-${worldStatus}`}>{statusCopy.label}</span>
                  </div>
                  <div><Icon name="wallet" size={20} /><span><small>Saldo disponível</small><strong>{formattedWallet}</strong></span></div>
                  <div><Icon name="shield" size={20} /><span><small>Proteção</small><strong>Backup automático</strong></span></div>
                </div>

                <div className="command-table-grid">
                  <aside className="world-side-panel friends-panel">
                    <div className="side-panel-heading"><Icon name="users" size={20} /><h3>Amigos</h3></div>
                    <strong>{isDemo ? "3 prontos" : "Grupo conectado"}</strong>
                    <ul>
                      {(isDemo ? ["Leonardo", "Ana", "Bia"] : ["Você"]).map((name, index) => (
                        <li key={name}><span>{name[0]}</span><div><strong>{name}</strong><small>{index < 3 ? "Pronto para jogar" : "Offline"}</small></div><i aria-hidden="true" /></li>
                      ))}
                    </ul>
                    <button onClick={() => navigateToSection("members")} type="button">Gerenciar grupo <Icon name="arrow-right" size={15} /></button>
                  </aside>

                  <div className="console-world-center">
                    <div className="console-world-visual" aria-hidden="true">
                      <span className="world-ring ring-outer" />
                      <span className="world-ring ring-inner" />
                      <Image alt="" height={1254} priority sizes="(max-width: 760px) 76vw, 500px" src="/world-map.png" unoptimized width={1254} />
                    </div>
                    <div className="console-world-identity">
                      <span className="game-label">PALWORLD · {(world?.region ?? "sa-east-1").toUpperCase()}</span>
                      <h2>{world?.name ?? "Nenhum World"}</h2>
                      <span className={`world-status status-${worldStatus}`}><Icon name={statusCopy.icon} size={15} />{statusCopy.label}</span>
                      <p>{statusCopy.detail}</p>
                    </div>
                    {["waking", "going_to_sleep"].includes(worldStatus) && (
                      <section aria-live="polite" className="operation-progress" role="status">
                        {operationProgress ? <>
                          <header>
                            <div><strong>{operationProgress.label}</strong><span>Etapa {operationProgress.current} de {operationProgress.total}</span></div>
                            <p>{operationProgress.detail}</p>
                          </header>
                          <ol aria-label={worldStatus === "waking" ? "Etapas do despertar" : "Etapas do sono seguro"}>
                            {operationProgress.steps.map((step) => (
                              <li className={`operation-step step-${step.state}`} key={step.phase}>
                                <span className="operation-step-marker">{step.state === "complete" ? <Icon name="check" size={13} /> : <i aria-hidden="true" />}</span>
                                <span><strong>{step.label}</strong>{step.state === "current" && <small>{step.detail}</small>}</span>
                              </li>
                            ))}
                          </ol>
                          <footer><Icon name="clock" size={14} /><span>Iniciado às {operationProgress.startedAt}. Você pode sair desta tela sem interromper o preparo.</span></footer>
                        </> : <>
                          <header><div><strong>Sincronizando o preparo</strong><span>Operação persistida</span></div><p>Buscando a etapa mais recente do World.</p></header>
                          <footer><Icon name="clock" size={14} /><span>A Console continuará acompanhando automaticamente.</span></footer>
                        </>}
                      </section>
                    )}
                    {worldStatus === "needs_attention" && (
                      <div className="operation-progress operation-attention" role="status">
                        <div><span>A inicialização foi encerrada com segurança</span><strong>Ação necessária</strong></div>
                        <p>{latestOperation?.status === "needs_attention" ? "O runtime não chegou a ficar disponível. A reserva não utilizada volta para a Wallet." : "A GameWake protegeu o World e liberou o runtime. Você pode tentar novamente."}</p>
                      </div>
                    )}
                  </div>

                  <aside className="world-side-panel discord-panel">
                    <div className="side-panel-heading"><Icon name="discord" size={21} /><h3>Discord</h3></div>
                    <code>/gamewake acordar</code>
                    <p>A turma acompanha restauração, conexão e sono seguro no canal.</p>
                    <div className="discord-protection"><Icon name="shield" size={17} /><span><strong>Dados privados</strong><small>Endereço e senha só aparecem para quem pode conectar.</small></span></div>
                  </aside>
                </div>

                {can("world:edit") && <label className="auto-sleep-setting">
                  <span><strong>Auto Sleep</strong><small>Dorme com save seguro quando o servidor fica vazio.</small></span>
                  <select
                    aria-label="Auto Sleep"
                    disabled={!world}
                    onChange={(event) => void updateAutoSleep(event.target.value)}
                    value={world?.autoSleepMinutes === null ? "off" : String(world?.autoSleepMinutes ?? 20)}
                  >
                    <option value="10">10 minutos</option>
                    <option value="20">20 minutos</option>
                    <option value="30">30 minutos</option>
                    <option value="60">60 minutos</option>
                    <option value="off">Desligado · gera alerta de custo</option>
                  </select>
                </label>}

                <div className="world-action-dock">
                  <div className="world-stats">
                    <div><small>Última sessão</small><strong>{isDemo ? "Ontem · 2h 38min" : "Consulte em Atividade"}</strong></div>
                    <div><small>Save</small><strong>Verificado no sono seguro</strong></div>
                    <div><small>Preço</small><strong>Confirmado ao acordar</strong></div>
                  </div>
                  <div className="world-actions">
                    {can("world:wake") && <button className="button button-primary wake-button" data-testid="wake-world" disabled={!["sleeping", "needs_attention"].includes(worldStatus)} onClick={wakeWorld} type="button">
                      <Icon name="power" size={18} />
                      {worldStatus === "sleeping" ? "Acordar World" : worldStatus === "needs_attention" ? "Tentar novamente" : statusCopy.label}
                    </button>}
                    {worldStatus === "online" && (
                      <>
                        <button className="button button-primary" data-testid="connect-world" onClick={connectWorld} type="button"><Icon name="globe" size={18} />Conectar</button>
                        {can("world:sleep_when_empty") && <button className="button button-quiet-dark" data-testid="sleep-world" onClick={sleepWorld} type="button"><Icon name="moon" size={18} />Dormir com segurança</button>}
                      </>
                    )}
                    {can("world:edit") && <button className="button button-quiet-dark" onClick={() => navigateToSection("configuration")} type="button"><Icon name="settings" size={18} />Configurar</button>}
                    <button className="icon-button" aria-label="Mais ações" type="button"><Icon name="menu" size={18} /></button>
                  </div>
                </div>
              </section>}

              <div className="overview-grid console-support-strip">
                <article className="overview-card">
                  <div className="card-heading"><div><span className="card-symbol"><Icon name="wallet" size={18} /></span><h3>Wallet</h3></div><button onClick={() => navigateToSection("wallet")} type="button">Ver extrato <Icon name="arrow-right" size={14} /></button></div>
                  <strong className="overview-balance">{formattedWallet}</strong>
                  <p>Saldo disponível para as próximas sessões</p>
                  {reservedWalletAmount > 0 && <p className="reservation-note">{formattedReservedWallet} reservados temporariamente</p>}
                  <div className="meter wallet-meter"><span /></div>
                  <small>Balance Guard ativo · sono seguro reservado</small>
                </article>
                <article className="overview-card">
                  <div className="card-heading"><div><span className="card-symbol"><Icon name="users" size={18} /></span><h3>Grupo</h3></div><button onClick={() => navigateToSection("members")} type="button">Gerenciar <Icon name="arrow-right" size={14} /></button></div>
                  <div className="member-stack" aria-label={isDemo ? "5 membros" : "Grupo GameWake"}>
                    {isDemo ? <><span>L</span><span>A</span><span>B</span><span>C</span><span>+1</span></> : <span>GW</span>}
                  </div>
                  <strong>{isDemo ? "5 amigos com acesso" : "Acesso simples para os amigos"}</strong>
                  <p>{isDemo ? "1 Owner · 1 Manager · 3 Players" : "Player, Manager, Owner e Roles personalizadas"}</p>
                </article>
                <article className="overview-card activity-preview">
                  <div className="card-heading"><div><span className="card-symbol"><Icon name="activity" size={18} /></span><h3>Atividade recente</h3></div><button onClick={() => navigateToSection("activity")} type="button">Ver tudo <Icon name="arrow-right" size={14} /></button></div>
                  <ul>
                    <li><span className="event-dot green" /><div><strong>Backup verificado</strong><small>Ontem, 23:42</small></div></li>
                    <li><span className="event-dot amber" /><div><strong>World entrou em sono seguro</strong><small>Ontem, 23:41</small></div></li>
                    <li><span className="event-dot blue" /><div><strong>Ana aceitou o convite</strong><small>Segunda, 19:08</small></div></li>
                  </ul>
                </article>
              </div>
            </>
          )}

          {activeSection === "wallet" && (
            <div className="panel-page" data-testid="wallet-panel">
              <div className="panel-heading"><div><h1>Créditos do grupo</h1><p>Todo valor é explicado em um ledger imutável. A Wallet nunca fica negativa.</p></div></div>
              <div className="wallet-layout">
                <article className="balance-panel"><small>Saldo disponível</small><strong>{formattedWallet}</strong><span>BRL</span>{reservedWalletAmount > 0 && <p className="balance-reservation">{formattedReservedWallet} reservados temporariamente · não é cobrança</p>}<div className="guard-status"><i /> Balance Guard ativo</div></article>
                <article className="contribution-panel">
                  <h2>Adicionar créditos</h2>
                  <p>Escolha um pacote. O checkout Pix abre de forma privada na AbacatePay.</p>
                  <div className="amount-options" role="group" aria-label="Valor da contribuição">
                    {[25, 50, 100].map((amount) => <button className={contribution === amount ? "selected" : ""} key={amount} onClick={() => setContribution(amount)} type="button">R$ {amount}</button>)}
                  </div>
                  <button className="button button-primary full-button" data-testid="create-checkout" disabled={checkoutLoading} onClick={() => void createCheckout()} type="button">{checkoutLoading ? "Abrindo checkout Pix…" : `Contribuir R$ ${contribution},00`}</button>
                </article>
              </div>
              {world && can("world:budget:manage") && (
                <article className="budget-panel">
                  <div>
                    <span className="section-index">WORLD BUDGET · {world.name}</span>
                    <h2>Limite mensal de uso</h2>
                    <p>Ao chegar a 100%, o Balance Guard inicia o sono seguro e bloqueia novos despertares.</p>
                  </div>
                  <div className="budget-summary">
                    <strong>{worldBudget ? `${Number(worldBudget.percentage).toFixed(0)}%` : "Sem limite"}</strong>
                    <span>{worldBudget ? `${new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(worldBudget.committed))} de ${new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(worldBudget.monthlyLimit))}` : "Defina um limite para este World"}</span>
                  </div>
                  <div className="budget-controls">
                    <label>Limite mensal em BRL<input aria-label="Limite mensal do World" inputMode="decimal" min="0.01" onChange={(event) => setBudgetLimit(event.target.value)} step="0.01" type="number" value={budgetLimit} /></label>
                    <button className="button button-primary" onClick={() => void saveWorldBudget()} type="button">{saved ? "Orçamento salvo ✓" : "Salvar orçamento"}</button>
                  </div>
                </article>
              )}
              <article className="table-card">
                <div className="card-heading"><h2>Extrato</h2><span>Ledger imutável</span></div>
                <table>
                  <thead><tr><th>Data</th><th>Movimentação</th><th>Referência</th><th>Valor</th></tr></thead>
                  <tbody>
                    {(isDemo ? [
                      { id: "demo-1", type: "runtime_charge", amount: "-4.87", reference: "Palpagos", occurredAt: "2026-07-30T23:41:00Z" },
                      { id: "demo-2", type: "contribution", amount: "25.00", reference: "Ana", occurredAt: "2026-07-28T19:03:00Z" },
                    ] : walletStatement).map((entry) => {
                      const amount = Number(entry.amount);
                      return <tr key={entry.id}><td>{new Date(entry.occurredAt).toLocaleDateString("pt-BR")}</td><td>{entry.type.replaceAll("_", " ")}</td><td>{entry.reference}</td><td className={amount < 0 ? "negative" : "positive"}>{amount < 0 ? "− " : "+ "}{new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Math.abs(amount))}</td></tr>;
                    })}
                    {!isDemo && walletStatement.length === 0 && <tr><td colSpan={4}>Nenhuma movimentação ainda.</td></tr>}
                  </tbody>
                </table>
              </article>
            </div>
          )}

          {activeSection === "members" && (
            <div className="panel-page" data-testid="members-panel">
              <div className="panel-heading split"><div><h1>Grupo e Discord</h1><p>Prepare os comandos do servidor, convide amigos e controle quem pode fazer o quê.</p></div><span className="viewer-role-badge">Você é {viewerRole}</span></div>
              {can("integration:manage") && <DiscordSetupPanel accountId={accountId} accountName={accountName} channelConfigured={discordChannelConfigured} checking={discordCheckLoading} discordGuildId={discordGuildId} onRefresh={refreshDiscordIntegration} verificationMessage={discordVerificationMessage} />}
              {(can("membership:manage") || can("role:manage")) && <>
              <article className="contribution-panel invitation-builder">
                <h2>Criar link de convite</h2>
                <p>O amigo entra com o Discord, aceita uma vez e chega direto ao lugar certo.</p>
                <div className="invitation-access-picker" role="group" aria-label="Tipo de acesso do convite">
                  <button aria-pressed={inviteAccess === "play"} className={inviteAccess === "play" ? "selected" : ""} onClick={() => { setInviteAccess("play"); setInvitationLink(""); }} type="button"><Icon name="globe" size={18} /><span><strong>Só jogar</strong><small>Entrar, acordar e conectar ao World</small></span></button>
                  <button aria-pressed={inviteAccess === "console"} className={inviteAccess === "console" ? "selected" : ""} onClick={() => { setInviteAccess("console"); setInvitationLink(""); }} type="button"><Icon name="shield" size={18} /><span><strong>Gerenciar Console</strong><small>Acesso conforme a Role escolhida</small></span></button>
                </div>
                <div className="invitation-create-row">
                  {inviteAccess === "console" && <label>Role ao aceitar<select aria-label="Role do link de gerenciamento" onChange={(event) => setInviteRole(event.target.value)} value={inviteRole}><option value="predefined:manager">Moderador</option>{customRoles.map((role) => <option key={role.id} value={`custom:${role.id}`}>{role.name}</option>)}</select></label>}
                  <button className="button button-primary" data-testid="create-invitation-link" disabled={invitationLoading} onClick={() => void createInvitationLink()} type="button"><Icon name="plus" size={17} />{invitationLoading ? "Criando link…" : `Criar link para ${inviteAccess === "play" ? "jogar" : "gerenciar"}`}</button>
                </div>
                {inviteAccess === "console" && <small>Por segurança, links de gerenciamento exigem que seu login Discord tenha sido renovado recentemente. <Link href={`/auth/discord/start?install=0&accountId=${encodeURIComponent(accountId)}`}>Renovar login</Link></small>}
                {invitationLink && <div className="invitation-link-result" role="status"><label>Link pronto<input aria-label="Link de convite criado" readOnly value={invitationLink} /></label><button className="button button-outline" onClick={() => void copyInvitationLink()} type="button">{invitationCopied ? "Link copiado ✓" : "Copiar link"}</button><small>Expira em 7 dias e funciona uma única vez.</small></div>}
                <div className="discord-command-guide"><Icon name="discord" size={19} /><p><strong>Quer convidar dentro do Discord?</strong> Use <code>/gamewake convidar @amigo1 @amigo2</code>. Esses convites dão acesso Player.</p></div>
              </article>
              <article className="table-card">
                <div className="card-heading"><h2>Seu grupo</h2><span>{isDemo ? invites.length + 2 : memberships.length} membros</span></div>
                {isDemo ? <><div className="member-row"><span className="avatar">L</span><div><strong>Leonardo</strong><small>Você · Discord conectado</small></div><span className="role role-owner">Owner</span></div>{invites.map((name) => <div className="member-row" key={name}><span className="avatar pastel">{name[0]}</span><div><strong>{name}</strong><small>Discord conectado</small></div><span className="role">Player</span></div>)}</> : memberships.map((membership) => (
                  <div className="member-row" key={membership.id}>
                    <span className="avatar pastel">{membership.userId[0]?.toUpperCase()}</span>
                    <div><strong>{membership.userId}</strong><small>{membership.roles.length === 0 ? "Sem permissões até receber uma Role" : membership.roles.some((role) => role.worldId) ? "Acesso limitado por World" : "Acesso à conta"}</small></div>
                    <div className="role-list">
                      {membership.roles.length === 0 && <span className="role role-empty">Sem Role</span>}
                      {membership.roles.map((role) => (
                        <span className={`role role-${role.role}`} key={role.id}>
                          {roleLabel(role.role, customRoles)}
                          <button aria-label={`Remover Role ${role.role} de ${membership.userId}`} onClick={() => beginMemberAction({ kind: "remove-role", membershipId: membership.id, roleAssignmentId: role.id, userId: membership.userId })} type="button"><Icon name="close" size={12} /></button>
                        </span>
                      ))}
                    </div>
                    <div className="role-controls">
                      <select aria-label={`Nova Role para ${membership.userId}`} onChange={(event) => setRoleSelections((current) => ({ ...current, [membership.id]: event.target.value }))} value={roleSelections[membership.id] ?? ""}><option value="">{membership.roles.length > 0 ? "Trocar Role…" : "Definir Role…"}</option><option value="predefined:player">Player</option><option value="predefined:manager">Moderador</option><option value="predefined:owner">Owner</option>{customRoles.map((role) => <option key={role.id} value={`custom:${role.id}`}>{role.name}</option>)}</select>
                      <div><button disabled={!roleSelections[membership.id]} onClick={() => beginRoleAssignment(membership.id)} type="button">{membership.roles.length > 0 ? "Trocar" : "Definir"}</button><button aria-label={`Remover membro ${membership.userId}`} className="danger-link" onClick={() => beginMemberAction({ kind: "remove-membership", membershipId: membership.id, userId: membership.userId })} type="button">Remover</button></div>
                    </div>
                    {pendingRoleAssignment === membership.id && <div className="role-confirmation-panel"><div><strong>Confirmar nova Role</strong><p>Você vai atribuir {roleLabel((roleSelections[membership.id] ?? "").split(":", 2)[1] ?? "", customRoles)} a {membership.userId}.</p></div><label>Digite o nome do grupo<input aria-label={`Confirme ${accountName} para atribuir Role a ${membership.userId}`} autoFocus onChange={(event) => setConfirmationName(event.target.value)} placeholder={accountName} value={confirmationName} /></label>{roleActionError && <p className="field-error" role="alert">{roleActionError}</p>}<div className="role-confirmation-actions"><button className="button button-primary" onClick={() => void assignRole(membership.id)} type="button">Confirmar atribuição</button><button className="button button-outline" onClick={() => { setPendingRoleAssignment(null); setRoleActionError(""); }} type="button">Cancelar</button><Link href={`/auth/discord/start?install=0&accountId=${encodeURIComponent(accountId)}`}>Renovar login Discord</Link></div></div>}
                    {pendingMemberAction?.membershipId === membership.id && <div className="role-confirmation-panel"><div><strong>{pendingMemberAction.kind === "remove-role" ? `Remover Role de ${membership.userId}` : `Remover ${membership.userId} do grupo`}</strong><p>{pendingMemberAction.kind === "remove-role" ? "O jogador ficará sem permissões até você definir outra Role." : "A Membership e o acesso aos Worlds serão removidos imediatamente."}</p></div><label>Digite o nome do grupo<input aria-label={pendingMemberAction.kind === "remove-role" ? `Confirme ${accountName} para remover Role de ${membership.userId}` : `Confirme ${accountName} para remover ${membership.userId}`} autoFocus onChange={(event) => setMemberActionConfirmation(event.target.value)} placeholder={accountName} value={memberActionConfirmation} /></label>{memberActionError && <p className="field-error" role="alert">{memberActionError}</p>}<div className="role-confirmation-actions"><button className="button button-danger" disabled={memberActionLoading} onClick={() => void confirmMemberAction()} type="button">{memberActionLoading ? "Removendo…" : pendingMemberAction.kind === "remove-role" ? "Confirmar remoção da Role" : "Confirmar remoção do jogador"}</button><button className="button button-outline" disabled={memberActionLoading} onClick={() => { setPendingMemberAction(null); setMemberActionError(""); }} type="button">Cancelar</button><Link href={`/auth/discord/start?install=0&accountId=${encodeURIComponent(accountId)}`}>Renovar login Discord</Link></div></div>}
                  </div>
                ))}
              </article>
              <details className="advanced-roles" open={!isDemo && customRoles.length > 0}>
                <summary>Permissões avançadas e Roles personalizadas</summary>
                <p>Cada pessoa usa uma única Role. Ao trocar, a nova Role substitui a anterior. Criar uma Role exige um login Discord renovado nos últimos cinco minutos.</p>
                {customRoles.map((role) => <div className="member-row" key={role.id}><span className="avatar pastel-purple">R</span><div><strong>{role.name}</strong><small>{role.permissions.map((permission) => permissionLabels[permission] ?? permission).join(" · ")}</small></div><span className="role">Personalizada</span></div>)}
                {!isDemo && <div className="contribution-panel custom-role-form">
                  <label>Nome da Role personalizada<input aria-label="Nome da Role personalizada" onChange={(event) => setCustomRoleName(event.target.value)} value={customRoleName} /></label>
                  <div className="amount-options role-permissions" role="group" aria-label="Permissões da Role">{availablePermissions.map((permission) => <label key={permission}><input checked={customRolePermissions.includes(permission)} onChange={(event) => setCustomRolePermissions((current) => event.target.checked ? [...current, permission] : current.filter((item) => item !== permission))} type="checkbox" />{permissionLabels[permission] ?? permission}</label>)}</div>
                  <label>Confirme com o nome do grupo<input aria-label={`Confirme ${accountName} para criar Role`} onChange={(event) => setCustomRoleConfirmation(event.target.value)} placeholder={accountName} value={customRoleConfirmation} /></label>
                  {customRoleError && <p className="field-error" role="alert">{customRoleError}</p>}
                  <div className="custom-role-actions"><button className="button button-outline" disabled={customRoleLoading || !customRoleName.trim() || customRolePermissions.length === 0} onClick={() => void createCustomRole()} type="button">{customRoleLoading ? "Criando Role…" : "Criar Role personalizada"}</button><Link href={`/auth/discord/start?install=0&accountId=${encodeURIComponent(accountId)}`}>Renovar login Discord</Link></div>
                </div>}
              </details>
              </>}
            </div>
          )}

          {activeSection === "configuration" && (
            <div className="panel-page" data-testid="configuration-panel">
              <div className="panel-heading split"><div><h1>Configuração</h1><p>Veja o impacto, os valores aceitos e a documentação oficial antes de alterar.</p></div><a className="button button-outline" href="https://tech.palworldgame.com/settings-and-operation/configuration/" rel="noreferrer" target="_blank">Documentação do Palworld <Icon name="arrow-right" size={16} /></a></div>
              <div className="config-notice"><span>i</span><p>As alterações criam uma revisão imutável e entram no próximo despertar. Se o World estiver Online, você poderá escolher uma reinicialização segura.</p></div>
              <fieldset className="world-password-card">
                <legend>Senha para entrar no World</legend>
                <p>A senha fica criptografada e nunca é exibida na configuração ou nos logs. Quem pode conectar a recebe apenas enquanto o World está Online.</p>
                <div className="password-mode-options">
                  <label>
                    <input
                      checked={passwordMode === "fixed"}
                      name="world-password-mode"
                      onChange={() => { setPasswordMode("fixed"); setPasswordError(""); setSaved(false); }}
                      type="radio"
                    />
                    <span><strong>Usar uma senha escolhida por mim</strong><small>Ela permanece igual até um Moderador ou Owner alterá-la.</small></span>
                  </label>
                  <label>
                    <input
                      checked={passwordMode === "random_each_run"}
                      name="world-password-mode"
                      onChange={() => { setPasswordMode("random_each_run"); setFixedPassword(""); setPasswordError(""); setSaved(false); }}
                      type="radio"
                    />
                    <span><strong>Gerar uma senha nova a cada despertar</strong><small>A senha muda somente quando uma nova sessão começa; repetir a mesma operação não a troca.</small></span>
                  </label>
                </div>
                {passwordMode === "fixed" && (
                  <label className="fixed-password-field">
                    Nova senha do World
                    <input
                      aria-describedby="fixed-password-help"
                      autoComplete="new-password"
                      maxLength={64}
                      minLength={6}
                      onChange={(event) => { setFixedPassword(event.target.value); setPasswordError(""); setSaved(false); }}
                      placeholder={savedPasswordMode === "fixed" ? "Deixe vazio para manter a senha atual" : "6 a 64 caracteres"}
                      type="password"
                      value={fixedPassword}
                    />
                    <small id="fixed-password-help">A senha atual nunca é revelada. Digite uma nova somente quando quiser substituí-la.</small>
                  </label>
                )}
                {passwordError && <p className="field-error" role="alert">{passwordError}</p>}
              </fieldset>
              <div className="config-grid">{liveConfigurationFields.map((field) => <article className="config-card" key={field.key}><div><span className="config-key">{field.key}</span><h2>{field.label}</h2><p>{field.impact}</p></div><label>Valor{field.valueType === "boolean" ? <select aria-label={field.label} onChange={(event) => setConfigurationValues((current) => ({ ...current, [field.key]: event.target.value === "true" }))} value={String(configurationValues[field.key] ?? field.default)}><option value="true">Ativado</option><option value="false">Desativado</option></select> : <input aria-label={field.label} onChange={(event) => setConfigurationValues((current) => ({ ...current, [field.key]: field.valueType === "string" ? event.target.value : Number(event.target.value) }))} type={field.valueType === "string" ? "text" : "number"} value={String(configurationValues[field.key] ?? field.default)} />}</label><small>Valores aceitos: <strong>{field.acceptedValues}</strong></small></article>)}</div>
              <div className="sticky-save"><div><strong>{liveConfigurationFields.length} opções validadas</strong><small>Uma revisão imutável será criada · reinicialização pode ser necessária</small></div><button className="button button-primary" data-testid="save-configuration" onClick={() => void saveConfiguration()} type="button">{saved ? "Configuração salva ✓" : "Revisar e salvar"}</button></div>
            </div>
          )}

          {activeSection === "backups" && (
            <div className="panel-page" data-testid="backups-panel">
              <div className="panel-heading split"><div><h1>Backups</h1><p>A última cópia recuperável nunca é removida. Restaurar sempre cria antes um ponto de retorno.</p></div><div className="world-actions">{can("backup:create") && <button aria-label="+ Backup manual" className="button button-primary" disabled={!isDemo && worldStatus !== "sleeping"} onClick={() => void createManualBackup()} type="button"><Icon name="plus" size={17} />Backup manual</button>}{can("world:export") && <button className="button button-outline" onClick={() => void exportWorld()} type="button">Exportar World</button>}</div></div>
              <article className="storage-card"><div><small>Armazenamento durável</small><strong>{isDemo ? "3 cópias protegidas" : `${backups.length} cópia${backups.length === 1 ? "" : "s"} protegida${backups.length === 1 ? "" : "s"}`}</strong></div><p>Backups, estado atual e exports usam armazenamento privado criptografado.</p>{exportUrl && <a className="button button-primary" href={exportUrl} rel="noreferrer">Baixar export privado</a>}</article>
              <article className="table-card backup-list">
                {(isDemo ? [{ id: "demo-backup", kind: "manual" as const, sizeBytes: 1_200_000_000, checksumVerified: true, createdAt: "2026-07-31T23:42:00Z" }] : backups).map((backup) => <div className="backup-row" key={backup.id}><span className="backup-icon"><Icon name={backup.checksumVerified ? "check" : "warning"} size={17} /></span><div><strong>{backupLabels[backup.kind]}</strong><small>{backup.createdAt ? new Date(backup.createdAt).toLocaleString("pt-BR") : "Data indisponível"} · {formatBytes(backup.sizeBytes)} · {backup.checksumVerified ? "checksum verificado" : "verificação pendente"}</small></div><span className={`backup-badge${backup.kind === "manual" ? " manual" : ""}`}>{backup.kind.toUpperCase()}</span>{can("backup:restore") && <button aria-label={`Restaurar ${backupLabels[backup.kind]}`} disabled={isDemo || worldStatus !== "sleeping"} onClick={() => void restoreBackup(backup.id)} type="button">Restaurar</button>}</div>)}
                {!isDemo && backups.length === 0 && <p>Nenhum Backup disponível. O primeiro será criado ao concluir o sono seguro.</p>}
              </article>
              {!isDemo && world && can("world:delete") && <details className="advanced-roles"><summary>Exclusão e portabilidade</summary>{worldStatus === "pending_deletion" ? <><p>Este World está em Pending Deletion por sete dias. O Backup final permanece protegido e você ainda pode exportar ou cancelar.</p><button className="button button-outline" onClick={() => void cancelWorldDeletion()} type="button">Cancelar exclusão</button></> : <><p>Excluir cria um Backup final e inicia sete dias de proteção. Confirme digitando o nome exato do World.</p><label>Nome do World<input aria-label="Confirme o nome do World" onChange={(event) => setDeletionConfirmation(event.target.value)} value={deletionConfirmation} /></label><button className="button button-outline" disabled={worldStatus !== "sleeping" || deletionConfirmation !== world.name} onClick={() => void scheduleWorldDeletion()} type="button">Agendar exclusão</button></>}</details>}
            </div>
          )}

          {activeSection === "activity" && (
            <div className="panel-page" data-testid="activity-panel">
              <div className="panel-heading"><div><h1>Atividade</h1><p>O grupo acompanha o que aconteceu sem expor senha, token ou dados de pagamento.</p></div></div>
              <article className="timeline-card">
                <div className="timeline-date">EVENTOS IMUTÁVEIS</div>
                {(isDemo ? [{ id: "demo-event", action: "role_assignment.revoked", actorUserId: "Leonardo", subjectId: "role-demo", occurredAt: "2026-07-31T23:42:00Z" }] : activityEvents).map((event) => <div className="timeline-row" key={event.id}><span className="event-dot blue" /><div><strong>{activityLabels[event.action] ?? event.action}</strong><p>Recurso {event.subjectId}. O payload é redigido na origem.</p><small>{new Date(event.occurredAt).toLocaleString("pt-BR")} · {event.actorUserId}</small></div></div>)}
                {!isDemo && worldOperations.map((operation) => <div className="timeline-row" key={operation.id}><span className="event-dot amber" /><div><strong>Operação de {operation.type}</strong><p>Fase {operation.phase.replaceAll("_", " ")} · {operation.status}</p><small>{new Date(operation.createdAt).toLocaleString("pt-BR")} · GameWake</small></div></div>)}
                {!isDemo && walletStatement.map((entry) => <div className="timeline-row" key={entry.id}><span className="event-dot green" /><div><strong>{entry.type.replaceAll("_", " ")}</strong><p>{entry.reference} · {new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(entry.amount))}</p><small>{new Date(entry.occurredAt).toLocaleString("pt-BR")} · Wallet Ledger</small></div></div>)}
                {!isDemo && activityEvents.length === 0 && worldOperations.length === 0 && walletStatement.length === 0 && <p>Nenhum evento registrado ainda.</p>}
              </article>
            </div>
          )}
          <footer className="console-legal-footer"><span>GameWake Closed Beta</span><div><Link href="/terms">Termos de Serviço</Link><Link href="/privacy">Política de Privacidade</Link></div></footer>
        </div>

        <nav className="mobile-nav" aria-label="Navegação móvel">
          {visibleSections.map((item) => <button className={activeSection === item.id ? "active" : ""} data-testid={`nav-${item.id}`} disabled={!hydrated} key={item.id} onClick={() => navigateToSection(item.id)} type="button"><span><Icon name={item.icon} size={19} /></span><small>{item.label.split(" ")[0]}</small></button>)}
        </nav>
      </section>
      {accountSwitcherOpen && (
        <div className="modal-backdrop">
          <section
            aria-label="Escolher grupo ou servidor"
            aria-modal="true"
            className="account-switch-dialog"
            role="dialog"
          >
            <div className="dialog-heading">
              <div><Icon name="discord" size={19} /><strong>Seus grupos GameWake</strong></div>
              <button aria-label="Fechar troca de grupo" onClick={() => setAccountSwitcherOpen(false)} type="button"><Icon name="close" size={19} /></button>
            </div>
            <p>Trocar entre grupos existentes não abre o Discord novamente. Cada grupo mostra somente os Worlds aos quais você tem acesso.</p>
            <div aria-busy={accountSwitcherLoading} className="account-choice-list">
              {accountSwitcherLoading && (
                <div
                  aria-label="Carregando grupos e Worlds"
                  className="account-choice-skeletons"
                  data-testid="account-switcher-skeleton"
                  role="status"
                >
                  <span className="sr-only">Buscando seus grupos e Worlds…</span>
                  {[0, 1, 2].map((item) => (
                    <span aria-hidden="true" className="account-choice-skeleton" key={item}>
                      <span className="skeleton-avatar" />
                      <span className="skeleton-copy"><span /><span /></span>
                      <span className="skeleton-action" />
                    </span>
                  ))}
                </div>
              )}
              {!accountSwitcherLoading && availableAccounts.filter((account) => account.worlds.length > 0).map((account) => (
                <Link
                  aria-current={account.id === accountId ? "page" : undefined}
                  href={`/accounts/${account.id}`}
                  key={account.id}
                  onClick={() => {
                    setGameWakeLastAccountId(account.id);
                    const preferredWorld = account.worlds.find((item) => item.id === getGameWakeLastWorldId(account.id)) ?? account.worlds[0];
                    if (preferredWorld) setGameWakeLastWorldId(account.id, preferredWorld.id);
                  }}
                >
                  <span className="account-avatar">{account.name[0]?.toUpperCase() ?? "G"}</span>
                  <span><strong>{account.name}</strong><small>{account.worlds.map((item) => item.name).join(" · ")}</small></span>
                  {account.id === accountId ? <em>Atual</em> : <Icon name="arrow-right" size={17} />}
                </Link>
              ))}
              {!accountSwitcherLoading && availableAccounts.filter((account) => account.worlds.length > 0).length === 0 && (
                <p>Nenhum outro grupo com World foi encontrado para esta conta.</p>
              )}
            </div>
            <Link className="button button-primary full-button" href="/auth/discord/start?install=1">
              <Icon name="plus" size={17} />Adicionar GameWake a outro servidor
            </Link>
            <small>Esta opção abre o Discord uma vez para você escolher e autorizar o novo servidor.</small>
          </section>
        </div>
      )}
      {profileMenuOpen && (
        <section aria-label="Menu do usuário" className="user-menu-popover" role="dialog">
          <header><span className="avatar avatar-small">{isDemo ? "L" : "V"}</span><span><strong>{isDemo ? "Leonardo" : "Você"}</strong><small>{viewerRole} em {accountName}</small></span></header>
          {signOutConfirmation ? (
            <div className="signout-confirmation">
              <strong>Sair desta sessão?</strong>
              <p>Você precisará entrar novamente com o Discord neste dispositivo.</p>
              <div><button className="button button-outline" onClick={() => setSignOutConfirmation(false)} type="button">Continuar conectado</button><button className="button button-primary" onClick={signOut} type="button">Confirmar saída</button></div>
            </div>
          ) : (
            <>
              <button className="user-menu-action" onClick={() => setSignOutConfirmation(true)} type="button"><Icon name="power" size={17} />Sair do GameWake</button>
              <button className="user-menu-close" onClick={() => setProfileMenuOpen(false)} type="button">Fechar menu</button>
            </>
          )}
        </section>
      )}
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
                <Icon name="close" size={19} />
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
            <button className="button button-primary full-button" onClick={() => void copyConnection()} type="button">
              {connectionCopied ? "Conexão copiada" : "Copiar conexão"}
            </button>
          </section>
        </div>
      )}
      {wakeEstimate && (
        <div className="modal-backdrop">
          <section
            aria-label={`Confirmar despertar de ${world?.name ?? "World"}`}
            aria-modal="true"
            className="connection-dialog"
            role="dialog"
          >
            <div className="dialog-heading">
              <strong>Preço desta sessão</strong>
              <button aria-label="Cancelar despertar" onClick={() => setWakeEstimate(null)} type="button"><Icon name="close" size={19} /></button>
            </div>
            <h2>{formatBrl(wakeEstimate.hourlyRate)} por hora</h2>
            <strong className="wake-reservation">{formatBrl(wakeEstimate.minimumReservation)} reservados agora</strong>
            <p>Esta reserva não é uma cobrança. Ela protege a inicialização, pelo menos 15 minutos online e o sono seguro durante {wakeEstimate.reservedMinutes} minutos. O valor não usado volta para a Wallet.</p>
            <button className="button button-primary full-button" onClick={() => void confirmWake()} type="button">Reservar {formatBrl(wakeEstimate.minimumReservation)} e acordar</button>
          </section>
        </div>
      )}
    </main>
  );
}
