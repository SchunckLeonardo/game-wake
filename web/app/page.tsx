import type { Metadata } from "next";
import Image from "next/image";
import { Icon } from "./Icon";

export const metadata: Metadata = {
  title: "Jogue quando quiser",
  description:
    "Mundos persistentes para jogar com seus amigos. A infraestrutura acorda quando vocês jogam e dorme quando terminam.",
};

const apiOrigin = (process.env.NEXT_PUBLIC_GAMEWAKE_API_URL ?? "").replace(/\/$/, "");
const discordSignIn = `${apiOrigin}/auth/discord/start`;

const friendInitials = ["L", "A", "B"];

function StepDiagram({ step }: { step: 1 | 2 | 3 }) {
  return (
    <svg aria-hidden="true" className="step-diagram" viewBox="0 0 260 92">
      {step === 1 && (
        <>
          <rect height="48" rx="6" width="72" x="4" y="22" />
          <path d="M17 37h30M17 49h42M17 61h24" />
          <circle cx="62" cy="37" r="3" />
          <path d="M82 46h27c9 0 9-16 18-16s9 32 18 32 9-16 18-16h13" />
          <circle cx="216" cy="46" r="38" />
          <path d="M178 46h76M216 8c-15 13-22 26-22 38s7 25 22 38M216 8c15 13 22 26 22 38s-7 25-22 38" />
        </>
      )}
      {step === 2 && (
        <>
          <circle cx="31" cy="31" r="13" /><path d="M8 79c1-20 9-31 23-31s22 11 23 31" />
          <circle cx="79" cy="31" r="13" /><path d="M56 79c1-20 9-31 23-31s22 11 23 31" />
          <circle cx="127" cy="31" r="13" /><path d="M104 79c1-20 9-31 23-31s22 11 23 31" />
          <path d="M157 46h30m-8-8 8 8-8 8" />
          <path d="M207 24c12-6 24-6 36 0l8 46c-13 10-39 10-52 0l8-46Z" />
          <circle cx="217" cy="49" r="3" /><circle cx="233" cy="49" r="3" /><path d="M216 62c6 4 12 4 18 0" />
        </>
      )}
      {step === 3 && (
        <>
          <circle cx="25" cy="33" r="12" /><path d="M5 78c1-18 7-28 20-28s19 10 20 28" />
          <circle cx="66" cy="33" r="12" /><path d="M46 78c1-18 7-28 20-28s19 10 20 28" />
          <circle cx="107" cy="33" r="12" /><path d="M87 78c1-18 7-28 20-28s19 10 20 28" />
          <path d="M132 46h23m-8-8 8 8-8 8" />
          <rect height="64" rx="6" width="88" x="168" y="12" />
          <path d="M178 24h68v40h-68zM198 82h28" />
          <circle cx="212" cy="44" r="12" /><path d="m206 44 5 5 9-11" />
        </>
      )}
    </svg>
  );
}

export default function Home() {
  return (
    <main className="landing-shell">
      <header className="landing-nav">
        <a className="brand" href="#top" aria-label="GameWake — início">
          <span className="brand-mark" aria-hidden="true">
            <Icon name="power" size={20} />
          </span>
          <span>GameWake</span>
        </a>
        <nav aria-label="Navegação principal">
          <a href="#como-funciona">Como funciona</a>
          <a href="#seguranca">Seu World</a>
          <a className="nav-login" href={discordSignIn}>
            <Icon name="discord" size={18} />
            Entrar
          </a>
        </nav>
      </header>

      <section className="hero world-table-hero" id="top">
        <div className="hero-intro">
          <h1>
            <span>Seu mundo fica.</span>
            A infraestrutura só acorda quando vocês vão jogar.
          </h1>
          <div className="hero-intro-copy">
            <p>
              Reúna os amigos no Discord, acorde o World em um comando e pague
              somente pelo tempo usado. O GameWake cuida da infraestrutura e
              mantém o save pronto para a próxima sessão.
            </p>
            <a className="text-link" href="#como-funciona">
              Entender o ciclo <Icon name="arrow-down" size={17} />
            </a>
          </div>
        </div>

        <div className="world-table" aria-label="Como o GameWake mantém seu World pronto">
          <article className="world-station station-friends">
            <span className="station-icon indigo"><Icon name="users" /></span>
            <div>
              <h2>Seus amigos</h2>
              <p>O grupo entra pelo Discord e cada pessoa recebe só o acesso necessário.</p>
              <div className="friend-presence" aria-label="Três amigos prontos">
                {friendInitials.map((initial) => (
                  <span key={initial}>
                    {initial}<i aria-hidden="true" />
                  </span>
                ))}
                <strong>3 prontos</strong>
              </div>
            </div>
          </article>

          <article className="world-station station-discord">
            <span className="station-icon indigo"><Icon name="discord" /></span>
            <div>
              <h2>Discord</h2>
              <p className="command-line"><code>/gamewake acordar</code></p>
              <p>Um comando inicia o ciclo e o grupo acompanha cada etapa.</p>
            </div>
          </article>

          <article className="world-station station-cost">
            <span className="station-icon amber"><Icon name="wallet" /></span>
            <div>
              <h2>Preço por hora</h2>
              <strong>Exemplo beta · R$ 5,50/h</strong>
              <p>Preço travado para a sessão e cobrança pelo tempo realmente usado.</p>
            </div>
          </article>

          <article className="world-station station-backup">
            <span className="station-icon coral"><Icon name="shield" /></span>
            <div>
              <h2>Save protegido</h2>
              <strong>Backup verificado</strong>
              <p>O World só dorme depois de salvar, validar e proteger o progresso.</p>
            </div>
          </article>

          <div className="world-stage">
            <span className="world-ring ring-dashed" aria-hidden="true" />
            <span className="world-ring ring-outer" aria-hidden="true" />
            <span className="world-ring ring-inner" aria-hidden="true" />
            <span className="orbit-marker marker-north" aria-hidden="true" />
            <span className="orbit-marker marker-east" aria-hidden="true" />
            <span className="orbit-marker marker-south" aria-hidden="true" />
            <span className="orbit-marker marker-west" aria-hidden="true" />
            <Image
              alt=""
              aria-hidden="true"
              className="world-map-image"
              height={1254}
              priority
              sizes="(max-width: 760px) 88vw, 560px"
              src="/world-map.png"
              unoptimized
              width={1254}
            />
            <div className="world-stage-card">
              <span><Icon name="moon" size={16} /> Dormindo com segurança</span>
              <strong>Palpagos</strong>
              <a className="button button-primary" href={discordSignIn}>
                <Icon name="discord" size={19} />
                Entrar com Discord
              </a>
            </div>
          </div>
        </div>

        <p className="hero-note">
          Cenário ilustrativo da closed beta para grupos de Palworld no Brasil · sem mensalidade de máquina parada
        </p>
      </section>

      <section className="steps-section" id="como-funciona">
        <div className="section-heading">
          <h2>Da vontade de jogar ao World online, sem burocracia.</h2>
          <p>O grupo só precisa conhecer três momentos. O resto acontece nos bastidores.</p>
        </div>
        <div className="step-grid">
          <article>
            <span className="step-number">1</span>
            <h3>Reúna o grupo</h3>
            <p>
              Conecte o servidor do Discord e convide vários amigos de uma vez.
              Player, Manager e Owner deixam os limites fáceis de entender.
            </p>
            <StepDiagram step={1} />
          </article>
          <article>
            <span className="step-number">2</span>
            <h3>Acorde o World</h3>
            <p>
              O GameWake restaura o save, aplica a configuração e só anuncia
              Online quando o jogo realmente aceita conexão.
            </p>
            <StepDiagram step={2} />
          </article>
          <article>
            <span className="step-number">3</span>
            <h3>Durma tranquilo</h3>
            <p>
              Ao terminar, salvamos, validamos e criamos o backup antes de
              liberar a máquina. O World continua sendo seu.
            </p>
            <StepDiagram step={3} />
          </article>
        </div>
      </section>

      <section className="pricing-story">
        <div className="pricing-copy">
          <h2>Pague pelo tempo de jogo, não por uma máquina parada.</h2>
          <p>
            Antes de acordar, você vê o preço final por hora. A Wallet pré-paga,
            o orçamento do World e os alertas de saldo impedem cobranças
            inesperadas.
          </p>
          <ul className="check-list">
            <li><Icon name="check" size={17} />Preço da sessão travado antes de iniciar</li>
            <li><Icon name="check" size={17} />Cobrança por segundo, com mínimo de 60 segundos</li>
            <li><Icon name="check" size={17} />Sono automático quando o World fica vazio</li>
            <li><Icon name="check" size={17} />Contribuições avulsas via Pix ou cartão</li>
          </ul>
        </div>
        <div className="wallet-card">
          <span className="demo-label">Exemplo ilustrativo</span>
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
          <Image alt="" height={1254} sizes="(max-width: 760px) 82vw, 460px" src="/world-map.png" unoptimized width={1254} />
          <span className="backup-node node-one"><Icon name="database" size={18} /></span>
          <span className="backup-node node-two"><Icon name="shield" size={18} /></span>
          <span className="backup-node node-three"><Icon name="check" size={18} /></span>
        </div>
        <div>
          <h2>A máquina é descartável. Seu progresso não.</h2>
          <p>
            Saves, configuração e backups vivem fora do Runtime. Mesmo quando a
            infraestrutura dorme, seu World permanece íntegro, verificável e
            pronto para ser restaurado.
          </p>
          <div className="safety-facts">
            <div><strong>7 dias</strong><span>para cancelar uma exclusão</span></div>
            <div><strong>Recuperação</strong><span>novas tentativas automáticas antes de pedir ajuda</span></div>
            <div><strong>Portabilidade</strong><span>export privado do save nativo</span></div>
          </div>
        </div>
      </section>

      <section className="closing-cta">
        <Icon name="power" size={32} />
        <h2>Menos tempo configurando.<br />Mais tempo jogando juntos.</h2>
        <a className="button button-primary" href={discordSignIn}>
          <Icon name="discord" size={19} />
          Entrar com Discord
        </a>
        <p>Closed beta para grupos de Palworld no Brasil.</p>
      </section>

      <footer>
        <a className="brand" href="#top">
          <span className="brand-mark brand-mark-small"><Icon name="power" size={15} /></span>
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
