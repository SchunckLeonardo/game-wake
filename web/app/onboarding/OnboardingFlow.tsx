"use client";

import { useState } from "react";
import Link from "next/link";
import { useHydrated } from "../useHydrated";

export function OnboardingFlow() {
  const hydrated = useHydrated();
  const [step, setStep] = useState(1);
  const [groupName, setGroupName] = useState("");
  const [worldName, setWorldName] = useState("");

  return (
    <main
      aria-busy={!hydrated}
      className="onboarding-shell"
      data-hydrated={hydrated ? "true" : "false"}
      data-testid="onboarding"
    >
      <header>
        <Link className="brand" href="/">
          <span className="brand-mark">G</span>
          <span>GameWake</span>
        </Link>
        <span>Passo {Math.min(step, 2)} de 2</span>
      </header>
      <div className="onboarding-progress"><span style={{ width: `${step * 50}%` }} /></div>
      <section className="onboarding-card">
        {step === 1 && (
          <>
            <span className="onboarding-symbol" aria-hidden="true">♙</span>
            <span className="section-index">SEU GRUPO</span>
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
            <span className="onboarding-symbol violet" aria-hidden="true">◉</span>
            <span className="section-index">PRIMEIRO WORLD</span>
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
            <div className="profile-choice"><span>Para até 8 amigos</span><strong>R$ 1,84/h</strong><small>Preço confirmado antes de cada sessão</small></div>
            <button
              className="button button-primary full-button"
              disabled={!worldName.trim()}
              onClick={() => setStep(3)}
              type="button"
            >
              Criar meu World
            </button>
          </>
        )}
        {step === 3 && (
          <div className="onboarding-success">
            <span aria-hidden="true">✓</span>
            <span className="section-index">GAMEWAKE CONFIGURADO</span>
            <h1>Tudo pronto para jogar</h1>
            <p><strong>{worldName}</strong> pertence ao grupo <strong>{groupName}</strong>. Agora convide os amigos ou acorde o World.</p>
            <div className="success-actions"><Link className="button button-primary" href="/accounts/demo?demo=1">Abrir Console</Link><button className="button button-outline" type="button">Convidar amigos</button></div>
          </div>
        )}
      </section>
      <p className="onboarding-foot">Seu save permanece seguro mesmo quando a máquina está dormindo.</p>
    </main>
  );
}
