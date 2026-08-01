"use client";

import { useCallback, useState } from "react";
import { ConsoleDashboard } from "../console/ConsoleDashboard";
import { gameWakeFetch } from "../gamewakeApi";
import { Icon } from "../Icon";
import { DiscordActivityBridge } from "./DiscordActivityBridge";

type AccountList = { accounts: Array<{ id: string }> };

export function DiscordActivityExperience() {
  const [accountId, setAccountId] = useState("demo");
  const [needsOnboarding, setNeedsOnboarding] = useState(false);

  const resolveAccount = useCallback(async () => {
    const response = await gameWakeFetch("/api/v1/me/accounts");
    const { accounts } = (await response.json()) as AccountList;
    if (accounts.length === 0) {
      setNeedsOnboarding(true);
      return;
    }
    setAccountId(accounts[0].id);
  }, []);

  return (
    <>
      <DiscordActivityBridge onAuthenticated={resolveAccount} />
      {needsOnboarding ? (
        <main className="onboarding-shell">
          <section className="onboarding-card">
            <span className="onboarding-symbol" aria-hidden="true"><Icon name="globe" size={23} /></span>
            <h1>Crie seu primeiro grupo</h1>
            <p>Abra a Console no navegador uma vez para concluir o onboarding.</p>
            <a className="button button-primary" href="/onboarding" target="_blank">
              Abrir onboarding
            </a>
          </section>
        </main>
      ) : (
        <ConsoleDashboard accountId={accountId} activityMode />
      )}
    </>
  );
}
