export const GAMEWAKE_SESSION_KEY = "gamewake_session";
export const GAMEWAKE_DISCORD_GUILD_ID_KEY = "gamewake_discord_guild_id";
export const GAMEWAKE_KNOWN_USER_KEY = "gamewake_known_user";
export const GAMEWAKE_LAST_ACCOUNT_KEY = "gamewake:last-account";
export const GAMEWAKE_POST_AUTH_RETURN_KEY = "gamewake:post-auth-return";

function migrateSessionValue(key: string) {
  const persisted = window.localStorage.getItem(key);
  if (persisted) return persisted;
  const legacy = window.sessionStorage.getItem(key);
  if (!legacy) return null;
  window.localStorage.setItem(key, legacy);
  window.sessionStorage.removeItem(key);
  return legacy;
}

export function getGameWakeSession() {
  return migrateSessionValue(GAMEWAKE_SESSION_KEY);
}

export function setGameWakeSession(session: string) {
  window.localStorage.setItem(GAMEWAKE_SESSION_KEY, session);
  window.localStorage.setItem(GAMEWAKE_KNOWN_USER_KEY, "true");
  window.sessionStorage.removeItem(GAMEWAKE_SESSION_KEY);
}

export function clearGameWakeSession() {
  window.localStorage.removeItem(GAMEWAKE_SESSION_KEY);
  window.sessionStorage.removeItem(GAMEWAKE_SESSION_KEY);
}

export function getGameWakeLastAccountId() {
  return window.localStorage.getItem(GAMEWAKE_LAST_ACCOUNT_KEY);
}

export function setGameWakeLastAccountId(accountId: string) {
  window.localStorage.setItem(GAMEWAKE_LAST_ACCOUNT_KEY, accountId);
}

function safePostAuthReturn(value: string | null) {
  if (!value || !/^\/accounts\/[A-Za-z0-9-]+(?:\/worlds\/[A-Za-z0-9-]+\/configuration)?(?:\?[^#]*)?$/.test(value)) {
    return null;
  }
  return value;
}

export function setGameWakePostAuthReturn(path: string) {
  const safePath = safePostAuthReturn(path);
  if (safePath) window.localStorage.setItem(GAMEWAKE_POST_AUTH_RETURN_KEY, safePath);
}

export function takeGameWakePostAuthReturn() {
  const path = safePostAuthReturn(window.localStorage.getItem(GAMEWAKE_POST_AUTH_RETURN_KEY));
  window.localStorage.removeItem(GAMEWAKE_POST_AUTH_RETURN_KEY);
  return path;
}

export function getGameWakeLastWorldId(accountId: string) {
  return window.localStorage.getItem(`gamewake:last-world:${accountId}`);
}

export function setGameWakeLastWorldId(accountId: string, worldId: string) {
  window.localStorage.setItem(`gamewake:last-world:${accountId}`, worldId);
}

export function getGameWakeDiscordGuildId() {
  return migrateSessionValue(GAMEWAKE_DISCORD_GUILD_ID_KEY);
}

export function setGameWakeDiscordGuildId(discordGuildId: string | null) {
  if (discordGuildId) {
    window.localStorage.setItem(GAMEWAKE_DISCORD_GUILD_ID_KEY, discordGuildId);
  } else {
    window.localStorage.removeItem(GAMEWAKE_DISCORD_GUILD_ID_KEY);
  }
  window.sessionStorage.removeItem(GAMEWAKE_DISCORD_GUILD_ID_KEY);
}

export function gameWakeApiUrl(path: string) {
  const base = (process.env.NEXT_PUBLIC_GAMEWAKE_API_URL ?? "").replace(/\/$/, "");
  return `${base}${path}`;
}

export async function gameWakeFetch(path: string, init: RequestInit = {}) {
  const session = getGameWakeSession();
  if (!session) throw new Error("Sua sessão expirou. Entre novamente com o Discord.");
  const headers = new Headers(init.headers);
  headers.set("authorization", `Bearer ${session}`);
  if (init.body && !headers.has("content-type")) {
    headers.set("content-type", "application/json");
  }
  let response: Response;
  try {
    response = await fetch(gameWakeApiUrl(path), { ...init, headers });
  } catch {
    throw new Error(
      "Não foi possível conectar ao GameWake. Verifique sua conexão e tente novamente.",
    );
  }
  if (!response.ok) {
    if (response.status === 401) clearGameWakeSession();
    let message = "Não foi possível concluir a ação.";
    try {
      const body = (await response.json()) as { error?: { message?: string } };
      message = body.error?.message ?? message;
    } catch {
      // Keep the safe generic message for non-JSON failures.
    }
    throw new Error(message);
  }
  return response;
}

export function gameWakeIdempotencyKey(action: string) {
  return `web:${action}:${crypto.randomUUID()}`;
}
