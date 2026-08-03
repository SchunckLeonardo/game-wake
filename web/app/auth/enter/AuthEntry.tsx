"use client";

import { useEffect, useState } from "react";
import { Icon } from "../../Icon";
import {
  GAMEWAKE_KNOWN_USER_KEY,
  clearGameWakeSession,
  gameWakeFetch,
  getGameWakeSession,
} from "../../gamewakeApi";

export function AuthEntry() {
  const [message, setMessage] = useState("Procurando sua sessão GameWake…");

  useEffect(() => {
    async function enter() {
      const session = getGameWakeSession();
      if (!session) {
        const returning = window.localStorage.getItem(GAMEWAKE_KNOWN_USER_KEY) === "true";
        window.location.replace(`/auth/discord/start?install=${returning ? "0" : "1"}`);
        return;
      }
      try {
        const response = await gameWakeFetch("/api/v1/me/accounts");
        const payload = (await response.json()) as { accounts: Array<{ id: string }> };
        window.location.replace(
          payload.accounts.length > 0 ? `/accounts/${payload.accounts[0].id}` : "/onboarding",
        );
      } catch {
        clearGameWakeSession();
        setMessage("Renovando sua entrada com o Discord…");
        window.location.replace("/auth/discord/start?install=0");
      }
    }

    void enter();
  }, []);

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
