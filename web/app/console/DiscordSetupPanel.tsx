"use client";

import { useState } from "react";
import Link from "next/link";
import { Icon } from "../Icon";
import { setGameWakePostAuthReturn } from "../gamewakeApi";

type DiscordSetupPanelProps = {
  accountId: string;
  accountName: string;
  channelConfigured: boolean;
  checking: boolean;
  discordGuildId: string | null;
  onRefresh: () => Promise<void>;
  verificationMessage: string;
};

const everydayCommands = [
  { command: "/gamewake status", purpose: "ver se o World está dormindo, acordando ou online" },
  { command: "/gamewake acordar", purpose: "preparar o World para a próxima partida" },
  { command: "/gamewake conectar", purpose: "receber IP e senha somente para você" },
];

export function DiscordSetupPanel({
  accountId,
  accountName,
  channelConfigured,
  checking,
  discordGuildId,
  onRefresh,
  verificationMessage,
}: DiscordSetupPanelProps) {
  const [copiedCommand, setCopiedCommand] = useState("");
  const installHref = `/auth/discord/start?install=1&accountId=${encodeURIComponent(accountId)}`;
  const discordHref = discordGuildId
    ? `https://discord.com/channels/${encodeURIComponent(discordGuildId)}`
    : null;

  function rememberReturn() {
    setGameWakePostAuthReturn(`${window.location.pathname}${window.location.search}`);
  }

  async function copyCommand(command: string) {
    await navigator.clipboard.writeText(command);
    setCopiedCommand(command);
    window.setTimeout(() => setCopiedCommand((current) => current === command ? "" : current), 2_500);
  }

  const installed = discordGuildId !== null;

  return (
    <article className="discord-setup" data-testid="discord-setup">
      <header className="discord-setup-heading">
        <span className="discord-setup-symbol" aria-hidden="true"><Icon name="discord" size={22} /></span>
        <div>
          <h2>Discord do grupo</h2>
          <p>Instale uma vez, ative o canal e depois seus amigos usam os comandos sem abrir a Console.</p>
        </div>
        <span className={`discord-readiness ${channelConfigured ? "ready" : installed ? "partial" : "pending"}`}>
          {channelConfigured ? "Pronto" : installed ? "Falta 1 passo" : "Não instalado"}
        </span>
      </header>

      <div className="discord-setup-layout">
        <ol className="discord-setup-journey" aria-label="Progresso da integração com o Discord">
          <li className={installed ? "done" : "current"}>
            <span>{installed ? <Icon name="check" size={15} /> : "1"}</span>
            <div><strong>Instalar no servidor</strong><small>{installed ? "Aplicativo vinculado ao grupo" : "Você escolhe o servidor no Discord"}</small></div>
          </li>
          <li className={channelConfigured ? "done" : installed ? "current" : "pending"}>
            <span>{channelConfigured ? <Icon name="check" size={15} /> : "2"}</span>
            <div><strong>Ativar um canal</strong><small>{channelConfigured ? "O GameWake já respondeu neste servidor" : "O Owner usa /gamewake comecar"}</small></div>
          </li>
          <li className={channelConfigured ? "current" : "pending"}>
            <span>3</span>
            <div><strong>Jogar pelos comandos</strong><small>Status, acordar e conexão privada</small></div>
          </li>
        </ol>

        <div className="discord-setup-action">
          {!installed && (
            <>
              <h3>Instale o GameWake no seu servidor</h3>
              <p>O Discord abrirá uma lista dos servidores que você pode gerenciar. Escolha onde seu grupo joga e confirme.</p>
              <div className="discord-zero-config">
                <Icon name="shield" size={17} />
                <span><strong>A GameWake cuida da parte técnica.</strong> Você não precisa configurar token, endpoint ou comando.</span>
              </div>
              <Link className="button button-primary" href={installHref} onClick={rememberReturn}>
                <Icon name="discord" size={17} />Escolher servidor no Discord
              </Link>
              <small>Você precisa ter a permissão <strong>Gerenciar Servidor</strong> no Discord.</small>
            </>
          )}

          {installed && !channelConfigured && (
            <>
              <h3>Ative o canal onde seus amigos jogam</h3>
              <p>Abra um canal de texto do servidor e execute este comando. O Owner faz isso uma única vez para ligar o grupo ao canal.</p>
              <div className="discord-command-copy">
                <code>/gamewake comecar</code>
                <button onClick={() => void copyCommand("/gamewake comecar")} type="button">
                  <Icon name={copiedCommand === "/gamewake comecar" ? "check" : "copy"} size={16} />
                  {copiedCommand === "/gamewake comecar" ? "Copiado" : "Copiar"}
                </button>
              </div>
              <div className="discord-expected-response">
                <span><Icon name="check" size={15} /></span>
                <p><strong>Como saber se funcionou</strong> O GameWake responderá “Conta do servidor pronta” e mostrará o botão da Console.</p>
              </div>
              <div className="discord-setup-actions">
                {discordHref && <a className="button button-primary" href={discordHref} rel="noreferrer" target="_blank"><Icon name="discord" size={17} />Abrir servidor no Discord</a>}
                <button className="button button-outline" disabled={checking} onClick={() => void onRefresh()} type="button">
                  <Icon name="activity" size={16} />{checking ? "Verificando…" : "Verificar novamente"}
                </button>
              </div>
              <p className="discord-owner-note">O Owner executa este comando uma única vez. Seus amigos não precisam repetir.</p>
              {verificationMessage && <p className="discord-verification" role="status">{verificationMessage}</p>}
              <details className="discord-troubleshooting">
                <summary>O comando /gamewake não aparece</summary>
                <ol>
                  <li>Confirme que você está no servidor escolhido para <strong>{accountName}</strong>.</li>
                  <li>Em Configurações do Servidor → Integrações → GameWake, permita comandos no canal atual.</li>
                  <li>Se o GameWake não estiver listado, repare a instalação abaixo.</li>
                </ol>
                <Link className="button button-outline" href={installHref} onClick={rememberReturn}>Reparar instalação</Link>
              </details>
            </>
          )}

          {channelConfigured && (
            <>
              <h3>Discord pronto para jogar</h3>
              <p>O GameWake já respondeu neste servidor. Agora o grupo pode começar com estes três comandos:</p>
              <div className="discord-command-list">
                {everydayCommands.map((item) => (
                  <div key={item.command}>
                    <code>{item.command}</code>
                    <span>{item.purpose}</span>
                    <button aria-label={`Copiar ${item.command}`} onClick={() => void copyCommand(item.command)} type="button">
                      <Icon name={copiedCommand === item.command ? "check" : "copy"} size={15} />
                    </button>
                  </div>
                ))}
              </div>
              <div className="discord-setup-actions">
                {discordHref && <a className="button button-primary" href={discordHref} rel="noreferrer" target="_blank"><Icon name="discord" size={17} />Testar no Discord</a>}
                <Link className="button button-outline" href={installHref} onClick={rememberReturn}>Trocar ou reparar servidor</Link>
              </div>
              <small>Para convidar: <code>/gamewake convidar @amigo1 @amigo2</code>. Cada amigo aceita uma vez com <code>/gamewake aceitar</code>.</small>
            </>
          )}
        </div>
      </div>
    </article>
  );
}
