"use client";

import type { MouseEvent, ReactNode } from "react";
import { useState } from "react";
import {
  GAMEWAKE_KNOWN_USER_KEY,
  clearGameWakeSession,
  gameWakeFetch,
  getGameWakeSession,
} from "./gamewakeApi";

type DiscordEntryLinkProps = {
  children: ReactNode;
  className?: string;
};

export function DiscordEntryLink({ children, className }: DiscordEntryLinkProps) {
  const [busy, setBusy] = useState(false);

  async function enter(event: MouseEvent<HTMLAnchorElement>) {
    event.preventDefault();
    if (busy) return;
    const session = getGameWakeSession();
    if (!session) {
      const returning = window.localStorage.getItem(GAMEWAKE_KNOWN_USER_KEY) === "true";
      window.location.assign(`/auth/discord/start?install=${returning ? "0" : "1"}`);
      return;
    }
    setBusy(true);
    try {
      const response = await gameWakeFetch("/api/v1/me/accounts");
      const payload = (await response.json()) as { accounts: Array<{ id: string }> };
      window.location.assign(
        payload.accounts.length > 0 ? `/accounts/${payload.accounts[0].id}` : "/onboarding",
      );
    } catch {
      clearGameWakeSession();
      window.location.assign("/auth/discord/start?install=0");
    }
  }

  return (
    <a
      aria-busy={busy}
      className={className}
      href="/auth/enter"
      onClick={enter}
    >
      {children}
    </a>
  );
}
