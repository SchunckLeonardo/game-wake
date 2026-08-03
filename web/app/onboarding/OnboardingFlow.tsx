"use client";

import { useState } from "react";
import Link from "next/link";
import { Icon } from "../Icon";
import {
  getGameWakeDiscordGuildId,
  gameWakeFetch,
  gameWakeIdempotencyKey,
  setGameWakeDiscordGuildId,
} from "../gamewakeApi";
import { useHydrated } from "../useHydrated";

export function OnboardingFlow() {
  const hydrated = useHydrated();
  const [step, setStep] = useState(1);
  const [groupName, setGroupName] = useState("");
  const [worldName, setWorldName] = useState("");
  const [accountId, setAccountId] = useState("demo");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);
  const [verifiedEmail, setVerifiedEmail] = useState("");

  async function createWorld() {
    if (!worldName.trim() || submitting) return;
    if (new URLSearchParams(window.location.search).get("demo") === "1") {
      setStep(3);
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const discordGuildId = getGameWakeDiscordGuildId();
      const accountResponse = await gameWakeFetch("/api/v1/accounts", {
        method: "POST",
        body: JSON.stringify({
          name: groupName.trim(),
          ...(discordGuildId ? { discordGuildId } : {}),
        }),
      });
      const account = (await accountResponse.json()) as {
        account: { id: string };
        ownerRecovery?: { verifiedEmail: string; codes: string[] } | null;
      };
      await gameWakeFetch(`/api/v1/accounts/${account.account.id}/worlds`, {
        method: "POST",
        body: JSON.stringify({
          name: worldName.trim(),
          gameTemplateId: "palworld:1",
          region: "sa-east-1",
          runtimeProfileId: "palworld-small",
          idempotencyKey: gameWakeIdempotencyKey("create-world"),
        }),
      });
      setAccountId(account.account.id);
      setRecoveryCodes(account.ownerRecovery?.codes ?? []);
      setVerifiedEmail(account.ownerRecovery?.verifiedEmail ?? "");
      setGameWakeDiscordGuildId(null);
      setStep(3);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Não foi possível criar o World.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main
      aria-busy={!hydrated}
      className="onboarding-shell"
      data-hydrated={hydrated ? "true" : "false"}
      data-testid="onboarding"
    >
      <header>
        <Link className="brand" href="/">
          <span className="brand-mark"><Icon name="power" size={19} /></span>
          <span>GameWake</span>
        </Link>
        <span>Passo {Math.min(step, 2)} de 2</span>
      </header>
      <div className="onboarding-progress"><span style={{ width: `${step * 50}%` }} /></div>
      <section className="onboarding-card">
        {step === 1 && (
          <>
            <span className="onboarding-symbol" aria-hidden="true"><Icon name="users" size={23} /></span>
            <h1>Como vocês se chamam?</h1>
            <p>Essa será a conta compartilhada dos amigos. Você poderá convidar todo mundo logo depois.</p>
            <label>
              Nome do grupo
              <input
                autoFocus
                disabled={!hydrated}
                onChange={(event) => setGroupName(event.target.value)}
                placeholder="Ex.: Sexta com os amigos"
                value={groupName}
              />
            </label>
            <button
              className="button button-primary full-button"
              disabled={!groupName.trim()}
              onClick={() => setStep(2)}
              type="button"
            >
              Continuar
            </button>
          </>
        )}
        {step === 2 && (
          <>
            <span className="onboarding-symbol violet" aria-hidden="true"><Icon name="globe" size={23} /></span>
            <h1>Onde a aventura vai continuar?</h1>
            <p>Escolha só o que importa para o jogo. O GameWake cuida do resto.</p>
            <label>
              Nome do World
              <input
                autoFocus
                disabled={!hydrated}
                onChange={(event) => setWorldName(event.target.value)}
                placeholder="Ex.: Palpagos"
                value={worldName}
              />
            </label>
            <div className="onboarding-options">
              <label>Jogo<select defaultValue="palworld"><option value="palworld">Palworld</option></select></label>
              <label>Região<select defaultValue="sa-east-1"><option value="sa-east-1">São Paulo · recomendado</option></select></label>
            </div>
            <div className="profile-choice"><span>Para até 8 amigos</span><strong>Pay-as-you-go</strong><small>Preço confirmado antes de cada sessão</small></div>
            {error && <p role="alert">{error}</p>}
            <button
              className="button button-primary full-button"
              disabled={!worldName.trim()}
              onClick={() => void createWorld()}
              type="button"
            >
              {submitting ? "Criando World…" : "Criar meu World"}
            </button>
          </>
        )}
        {step === 3 && (
          <div className="onboarding-success">
            <span aria-hidden="true"><Icon name="check" size={26} /></span>
            <h1>Tudo pronto para jogar</h1>
            <p><strong>{worldName}</strong> pertence ao grupo <strong>{groupName}</strong>. Agora convide os amigos ou acorde o World.</p>
            {recoveryCodes.length > 0 && (
              <div className="recovery-panel">
                <h2>Guarde seus códigos de recuperação</h2>
                <p>Proteção do Owner vinculada ao e-mail verificado {verifiedEmail}. Eles aparecem apenas agora.</p>
                <pre className="recovery-codes">{recoveryCodes.join("\n")}</pre>
              </div>
            )}
            <div className="success-actions"><Link className="button button-primary" href={accountId === "demo" ? "/accounts/demo?demo=1" : `/accounts/${accountId}`}>Abrir Console</Link><button className="button button-outline" type="button">Convidar amigos</button></div>
          </div>
        )}
      </section>
      <p className="onboarding-foot">Seu save permanece seguro mesmo quando a máquina está dormindo.</p>
    </main>
  );
}
