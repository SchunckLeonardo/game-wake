"use client";

import { useEffect, useState } from "react";
import {
  GAMEWAKE_DISCORD_GUILD_ID_KEY,
  GAMEWAKE_SESSION_KEY,
  gameWakeFetch,
} from "../../gamewakeApi";
import { Icon } from "../../Icon";

type AccountList = { accounts: Array<{ id: string }> };
type OwnerRecovery = {
  accountId: string;
  verifiedEmail: string;
  codes: string[];
};

function decodeRecovery(value: string | null): OwnerRecovery[] {
  if (!value) return [];
  try {
    const normalized = value.replaceAll("-", "+").replaceAll("_", "/");
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
    const decoded = JSON.parse(window.atob(padded));
    return Array.isArray(decoded) ? decoded : [];
  } catch {
    return [];
  }
}

export function AuthCallback() {
  const [message, setMessage] = useState("Validando sua conta do Discord…");
  const [ownerRecovery, setOwnerRecovery] = useState<OwnerRecovery[]>([]);
  const [destination, setDestination] = useState("/onboarding");

  useEffect(() => {
    async function finishSignIn() {
      const fragment = new URLSearchParams(window.location.hash.slice(1));
      const session = fragment.get("session");
      const recovery = decodeRecovery(fragment.get("ownerRecovery"));
      if (!session) {
        setMessage("O Discord não retornou uma sessão válida. Tente entrar novamente.");
        return;
      }
      window.sessionStorage.setItem(GAMEWAKE_SESSION_KEY, session);
      const discordGuildId = fragment.get("discordGuildId");
      if (discordGuildId && /^\d+$/.test(discordGuildId)) {
        window.sessionStorage.setItem(
          GAMEWAKE_DISCORD_GUILD_ID_KEY,
          discordGuildId,
        );
      } else {
        window.sessionStorage.removeItem(GAMEWAKE_DISCORD_GUILD_ID_KEY);
      }
      window.history.replaceState(null, "", window.location.pathname);
      try {
        const response = await gameWakeFetch("/api/v1/me/accounts");
        const { accounts } = (await response.json()) as AccountList;
        const next = accounts.length === 0 ? "/onboarding" : `/accounts/${accounts[0].id}`;
        if (recovery.length > 0) {
          setOwnerRecovery(recovery);
          setDestination(next);
          setMessage("Esses códigos aparecem apenas agora.");
          return;
        }
        window.location.replace(next);
      } catch (error) {
        window.sessionStorage.removeItem(GAMEWAKE_SESSION_KEY);
        setMessage(error instanceof Error ? error.message : "Não foi possível entrar.");
      }
    }

    void finishSignIn();
  }, []);

  if (ownerRecovery.length > 0) {
    return (
      <main className="onboarding-shell">
        <section className="onboarding-card">
          <span className="onboarding-symbol" aria-hidden="true"><Icon name="shield" size={23} /></span>
          <h1>Guarde seus códigos de recuperação</h1>
          <p>Seu e-mail verificado é <strong>{ownerRecovery[0].verifiedEmail}</strong>. Cada código funciona uma única vez; o GameWake não consegue exibi-los novamente.</p>
          <pre className="recovery-codes">{ownerRecovery.flatMap((item) => item.codes).join("\n")}</pre>
          <button className="button button-primary full-button" onClick={() => window.location.replace(destination)} type="button">Já guardei, continuar</button>
        </section>
      </main>
    );
  }

  return (
    <main className="onboarding-shell">
      <section aria-live="polite" className="onboarding-card" role="status">
        <span className="onboarding-symbol" aria-hidden="true"><Icon name="discord" size={23} /></span>
        <h1>Entrando no GameWake</h1>
        <p>{message}</p>
      </section>
    </main>
  );
}
