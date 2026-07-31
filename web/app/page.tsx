import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Jogue quando quiser",
  description:
    "Mundos persistentes para jogar com seus amigos. A infraestrutura acorda quando vocês jogam e dorme quando terminam.",
};

const discordSignIn = "/auth/discord/start?return_to=%2Fconsole";

export default function Home() {
  return (
    <main className="landing-shell">
      <header className="landing-nav">
        <a className="brand" href="#top" aria-label="GameWake — início">
          <span className="brand-mark" aria-hidden="true">
            G
          </span>
          <span>GameWake</span>
        </a>
        <nav aria-label="Navegação principal">
          <a href="#como-funciona">Como funciona</a>
          <a href="#seguranca">Seu mundo</a>
          <a className="nav-login" href={discordSignIn}>
            Entrar
          </a>
        </nav>
      </header>

      <section className="hero" id="top">
        <div className="hero-copy">
          <div className="eyebrow">
            <span className="pulse-dot" aria-hidden="true" />
            Closed beta · Palworld · Brasil
          </div>
          <h1>
            Seu mundo fica.
            <span>A infraestrutura só acorda quando vocês vão jogar.</span>
          </h1>
          <p className="hero-lead">
            Junte os amigos no Discord, acorde o servidor em um comando e pague
            somente quando estiverem jogando. Sem painel de provedor, sem
            infraestrutura para aprender.
          </p>
          <div className="hero-actions">
            <a className="button button-primary" href={discordSignIn}>
              <span aria-hidden="true">◉</span>
              Entrar com Discord
            </a>
            <a className="button button-quiet" href="#como-funciona">
              Ver como funciona <span aria-hidden="true">↓</span>
            </a>
          </div>
          <p className="hero-note">
            Convide o grupo inteiro de uma vez. Cada pessoa controla apenas o
            que você permitir.
          </p>
        </div>

        <div className="wake-demo" aria-label="Demonstração do GameWake no Discord">
          <div className="demo-topbar">
            <div className="demo-lights" aria-hidden="true">
              <span />
              <span />
              <span />
            </div>
            <span>sexta-com-os-amigos</span>
            <span className="encrypted-pill">privado</span>
          </div>
          <div className="discord-command">
            <div className="avatar">L</div>
            <div>
              <strong>Leonardo</strong>
              <p>
                <span>/gamewake</span> acordar
              </p>
            </div>
          </div>
          <div className="bot-card">
            <div className="bot-heading">
              <span className="brand-mark brand-mark-small">G</span>
              <div>
                <strong>GameWake</strong>
                <small>APP</small>
              </div>
              <span className="status-chip">ACORDANDO</span>
            </div>
            <h2>Palpagos está se preparando</h2>
            <div className="progress-track" aria-label="Progresso: restaurando mundo">
              <span />
            </div>
            <div className="progress-steps">
              <span className="step-done">Runtime pronto</span>
              <span className="step-active">Restaurando mundo</span>
              <span>Iniciando jogo</span>
            </div>
            <div className="demo-meta">
              <div>
                <small>Estimativa</small>
                <strong>~ 2 min</strong>
              </div>
              <div>
                <small>Preço travado</small>
                <strong>R$ 1,84/h</strong>
              </div>
            </div>
          </div>
          <div className="floating-backup">
            <span aria-hidden="true">✓</span>
            <div>
              <strong>Progresso protegido</strong>
              <small>Último backup verificado há 18 min</small>
            </div>
          </div>
        </div>
      </section>

      <section className="promise-strip" aria-label="Compromissos GameWake">
        <p>Um comando para jogar</p>
        <span aria-hidden="true">◆</span>
        <p>Wallet sem conta-surpresa</p>
        <span aria-hidden="true">◆</span>
        <p>Backup antes de desligar</p>
        <span aria-hidden="true">◆</span>
        <p>Seu save sempre portátil</p>
      </section>

      <section className="steps-section" id="como-funciona">
        <div className="section-heading">
          <span className="section-index">01 — COMO FUNCIONA</span>
          <h2>Da vontade de jogar ao World online, sem burocracia.</h2>
        </div>
        <div className="step-grid">
          <article>
            <span className="step-number">01</span>
            <div className="feature-icon" aria-hidden="true">◎</div>
            <h3>Crie com o Discord</h3>
            <p>
              Conecte o servidor do grupo e convide até três amigos no mesmo
              comando. Player, Manager e Owner mantêm tudo simples.
            </p>
          </article>
          <article>
            <span className="step-number">02</span>
            <div className="feature-icon" aria-hidden="true">↗</div>
            <h3>Acorde quando quiser</h3>
            <p>
              O GameWake restaura o World, aplica a configuração e só mostra
              Online quando o jogo realmente aceita conexão.
            </p>
          </article>
          <article>
            <span className="step-number">03</span>
            <div className="feature-icon" aria-hidden="true">⌁</div>
            <h3>Durma sem perder nada</h3>
            <p>
              Ao terminar, salvamos, validamos e criamos o backup antes de
              liberar a máquina. O World continua sendo seu.
            </p>
          </article>
        </div>
      </section>

      <section className="pricing-story">
        <div>
          <span className="section-index">02 — CUSTO TRANSPARENTE</span>
          <h2>Pague pelo tempo de jogo, não por uma máquina parada.</h2>
          <p>
            Antes de acordar, você vê o preço final por hora. A Wallet pré-paga,
            o orçamento do World e os alertas de saldo impedem cobranças
            inesperadas.
          </p>
          <ul className="check-list">
            <li>Preço da sessão travado antes de iniciar</li>
            <li>Cobrança por segundo, com mínimo de 60 segundos</li>
            <li>Sono automático quando o World fica vazio</li>
            <li>Contribuições avulsas via Pix ou cartão</li>
          </ul>
        </div>
        <div className="wallet-card">
          <div className="wallet-card-head">
            <span>Wallet do grupo</span>
            <span>BRL</span>
          </div>
          <strong className="wallet-balance">R$ 42,80</strong>
          <span className="wallet-caption">saldo disponível</span>
          <div className="session-line">
            <div>
              <span className="online-dot" />
              <strong>Palpagos</strong>
              <small>1h 12min online</small>
            </div>
            <strong>− R$ 2,21</strong>
          </div>
          <div className="budget-meter">
            <div><span>Orçamento de julho</span><strong>38%</strong></div>
            <div className="meter"><span /></div>
          </div>
          <p>Saldo estimado para mais 23 horas de jogo.</p>
        </div>
      </section>

      <section className="world-safety" id="seguranca">
        <div className="safety-visual" aria-hidden="true">
          <span className="orbit orbit-one" />
          <span className="orbit orbit-two" />
          <span className="world-core">WORLD</span>
          <span className="backup-node node-one">B1</span>
          <span className="backup-node node-two">B2</span>
          <span className="backup-node node-three">B3</span>
        </div>
        <div>
          <span className="section-index">03 — O WORLD É SEU</span>
          <h2>A máquina é descartável. Seu progresso não.</h2>
          <p>
            Saves, configuração e backups vivem fora do Runtime. Mesmo quando a
            infraestrutura dorme, seu World permanece íntegro, verificável e
            pronto para ser restaurado.
          </p>
          <div className="safety-facts">
            <div><strong>7 dias</strong><span>para cancelar uma exclusão</span></div>
            <div><strong>3×</strong><span>tentativas de recuperação automática</span></div>
            <div><strong>100%</strong><span>export portátil do save nativo</span></div>
          </div>
        </div>
      </section>

      <section className="closing-cta">
        <span className="section-index">PRONTO PARA A PRÓXIMA SESSÃO?</span>
        <h2>Menos tempo configurando.<br />Mais tempo jogando juntos.</h2>
        <a className="button button-primary" href={discordSignIn}>
          <span aria-hidden="true">◉</span>
          Entrar com Discord
        </a>
        <p>Closed beta para grupos de Palworld no Brasil.</p>
      </section>

      <footer>
        <a className="brand" href="#top">
          <span className="brand-mark brand-mark-small">G</span>
          <span>GameWake</span>
        </a>
        <p>Seu mundo continua. A infraestrutura só acorda para jogar.</p>
        <div>
          <a href="/termos">Termos</a>
          <a href="/privacidade">Privacidade</a>
          <a href="mailto:oi@gamewake.com.br">Contato</a>
        </div>
      </footer>
    </main>
  );
}
