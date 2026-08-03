"use client";

import { DiscordSDK } from "@discord/embedded-app-sdk";
import { useEffect, useState } from "react";
import { gameWakeApiUrl, setGameWakeSession } from "../gamewakeApi";

type ActivityStatus = "waiting" | "authorizing" | "ready" | "standalone" | "error";

type DiscordActivityBridgeProps = {
  onAuthenticated?: () => Promise<void> | void;
};

const statusMessages: Record<ActivityStatus, string> = {
  waiting: "Conectando ao Discord",
  authorizing: "Autorizando sua conta do Discord",
  ready: "Discord conectado",
  standalone: "Abra esta tela como uma Activity no Discord",
  error: "Não foi possível conectar ao Discord",
};

export function DiscordActivityBridge({ onAuthenticated }: DiscordActivityBridgeProps) {
  const [status, setStatus] = useState<ActivityStatus>("waiting");

  useEffect(() => {
    let active = true;

    async function authenticate() {
      await Promise.resolve();
      if (window.self === window.top) {
        if (active) setStatus("standalone");
        return;
      }
      const clientId = process.env.NEXT_PUBLIC_DISCORD_APPLICATION_ID;
      if (!clientId) {
        if (active) setStatus("error");
        return;
      }
      const discordSdk = new DiscordSDK(clientId);
      try {
        await discordSdk.ready();
        if (!active) return;
        setStatus("authorizing");
        const { code } = await discordSdk.commands.authorize({
          client_id: clientId,
          response_type: "code",
          state: crypto.randomUUID(),
          prompt: "none",
          scope: ["identify", "email", "guilds"],
        });
        const response = await fetch(
          gameWakeApiUrl("/api/v1/auth/discord/activity/token"),
          {
            method: "POST",
            credentials: "include",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({ code }),
          },
        );
        if (!response.ok) throw new Error("activity token exchange failed");
        const result = (await response.json()) as {
          accessToken?: string;
          session?: string;
        };
        if (!result.accessToken) throw new Error("activity token is missing");
        if (!result.session) throw new Error("GameWake session is missing");
        setGameWakeSession(result.session);
        await discordSdk.commands.authenticate({ access_token: result.accessToken });
        await onAuthenticated?.();
        if (active) setStatus("ready");
      } catch {
        if (active) setStatus("error");
      }
    }

    void authenticate();
    return () => {
      active = false;
    };
  }, [onAuthenticated]);

  return (
    <span
      aria-live="polite"
      className="sr-only"
      data-activity-auth={status}
      role="status"
    >
      {statusMessages[status]}
    </span>
  );
}
