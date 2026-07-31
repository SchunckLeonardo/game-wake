"use client";

import { useEffect, useState } from "react";
import {
  GAMEWAKE_SESSION_KEY,
  gameWakeFetch,
} from "../../gamewakeApi";

type AccountList = { accounts: Array<{ id: string }> };

export function AuthCallback() {
  const [message, setMessage] = useState("Validando sua conta do Discord…");

  useEffect(() => {
    async function finishSignIn() {
      const session = new URLSearchParams(window.location.hash.slice(1)).get("session");
      if (!session) {
        setMessage("O Discord não retornou uma sessão válida. Tente entrar novamente.");
        return;
      }
      window.sessionStorage.setItem(GAMEWAKE_SESSION_KEY, session);
      window.history.replaceState(null, "", window.location.pathname);
      try {
        const response = await gameWakeFetch("/api/v1/me/accounts");
        const { accounts } = (await response.json()) as AccountList;
        window.location.replace(
          accounts.length === 0 ? "/onboarding" : `/accounts/${accounts[0].id}`,
        );
      } catch (error) {
        window.sessionStorage.removeItem(GAMEWAKE_SESSION_KEY);
        setMessage(error instanceof Error ? error.message : "Não foi possível entrar.");
      }
    }

    void finishSignIn();
  }, []);

  return (
    <main className="onboarding-shell">
      <section aria-live="polite" className="onboarding-card" role="status">
        <span className="onboarding-symbol" aria-hidden="true">◉</span>
        <span className="section-index">DISCORD SIGN-IN</span>
        <h1>Entrando no GameWake</h1>
        <p>{message}</p>
      </section>
    </main>
  );
}
