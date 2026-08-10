"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Icon } from "../../../Icon";
import { gameWakeFetch, getGameWakeSession } from "../../../gamewakeApi";

type InvitationPreview = {
  id: string;
  accountName: string;
  access: "play" | "console";
  predefinedRole: string | null;
  customRoleId: string | null;
  status: "pending" | "accepted";
  expiresAt: string | null;
};

type InvitationAcceptanceProps = {
  accountId: string;
  invitationId: string;
};

function accessName(invitation: InvitationPreview) {
  if (invitation.access === "play") return "Player";
  if (invitation.predefinedRole === "manager") return "Moderador";
  return "Role personalizada";
}

export function InvitationAcceptance({
  accountId,
  invitationId,
}: InvitationAcceptanceProps) {
  const [preview, setPreview] = useState<InvitationPreview | null>(null);
  const [state, setState] = useState<"signed-out" | "loading" | "ready" | "accepting" | "error">(
    "loading",
  );
  const [message, setMessage] = useState("");

  useEffect(() => {
    let active = true;
    async function loadInvitation() {
      await Promise.resolve();
      if (!active) return;
      if (!getGameWakeSession()) {
        setState("signed-out");
        return;
      }
      try {
        const response = await gameWakeFetch(
          `/api/v1/accounts/${accountId}/invitations/${invitationId}`,
        );
        const payload = (await response.json()) as { invitation: InvitationPreview };
        if (!active) return;
        setPreview(payload.invitation);
        setState("ready");
      } catch (caught) {
        if (!active) return;
        setMessage(caught instanceof Error ? caught.message : "Este convite não está disponível.");
        setState("error");
      }
    }
    void loadInvitation();
    return () => {
      active = false;
    };
  }, [accountId, invitationId]);

  function signIn() {
    const path = `/convites/${accountId}/${invitationId}`;
    window.localStorage.setItem("gamewake:pending-invitation", path);
    window.location.assign("/auth/discord/start?install=0");
  }

  async function accept() {
    if (!preview || state === "accepting") return;
    setState("accepting");
    setMessage("");
    try {
      await gameWakeFetch(
        `/api/v1/accounts/${accountId}/invitations/${invitationId}/accept`,
        { method: "POST" },
      );
      window.location.replace(`/accounts/${accountId}`);
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Não foi possível aceitar o convite.");
      setState("error");
    }
  }

  return (
    <main className="invitation-shell">
      <section className="invitation-card" data-testid="invitation-acceptance">
        <Link className="brand" href="/" aria-label="GameWake — início">
          <span className="brand-mark"><Icon name="power" size={19} /></span>
          <span>GameWake</span>
        </Link>
        {state === "signed-out" && <>
          <span className="invitation-symbol"><Icon name="discord" size={24} /></span>
          <h1>Você recebeu um convite</h1>
          <p>Entre com o Discord para confirmar sua identidade e ver exatamente qual acesso será liberado.</p>
          <button className="button button-primary full-button" onClick={signIn} type="button">Entrar com Discord</button>
        </>}
        {state === "loading" && <p role="status">Carregando seu convite…</p>}
        {preview && state !== "signed-out" && <>
          <span className="invitation-symbol"><Icon name={preview.access === "play" ? "globe" : "shield"} size={24} /></span>
          <h1>{preview.access === "play" ? "Entre para jogar" : "Ajude a gerenciar o grupo"}</h1>
          <p><strong>{preview.accountName}</strong> convidou você para entrar como <strong>{accessName(preview)}</strong>.</p>
          <ul className="invitation-permissions">
            <li><Icon name="check" size={16} />Ver os Worlds do grupo</li>
            <li><Icon name="check" size={16} />Acordar e conectar para jogar</li>
            {preview.access === "console" && <li><Icon name="check" size={16} />Gerenciar somente o que a Role permitir</li>}
          </ul>
          <button className="button button-primary full-button" disabled={state === "accepting" || preview.status !== "pending"} onClick={() => void accept()} type="button">{state === "accepting" ? "Aceitando convite…" : preview.status === "pending" ? "Aceitar e continuar" : "Convite já utilizado"}</button>
          {preview.expiresAt && <small>Convite válido até {new Date(preview.expiresAt).toLocaleString("pt-BR")}.</small>}
        </>}
        {message && <div className="config-notice" role="alert"><span><Icon name="warning" size={15} /></span><p>{message}</p></div>}
      </section>
    </main>
  );
}
