export const GAMEWAKE_SESSION_KEY = "gamewake_session";
export const GAMEWAKE_DISCORD_GUILD_ID_KEY = "gamewake_discord_guild_id";

export function gameWakeApiUrl(path: string) {
  const base = (process.env.NEXT_PUBLIC_GAMEWAKE_API_URL ?? "").replace(/\/$/, "");
  return `${base}${path}`;
}

export async function gameWakeFetch(path: string, init: RequestInit = {}) {
  const session = window.sessionStorage.getItem(GAMEWAKE_SESSION_KEY);
  if (!session) throw new Error("Sua sessão expirou. Entre novamente com o Discord.");
  const headers = new Headers(init.headers);
  headers.set("authorization", `Bearer ${session}`);
  if (init.body && !headers.has("content-type")) {
    headers.set("content-type", "application/json");
  }
  const response = await fetch(gameWakeApiUrl(path), { ...init, headers });
  if (!response.ok) {
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
