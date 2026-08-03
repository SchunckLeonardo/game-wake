import type { ReactNode } from "react";
import Link from "next/link";
import { Icon } from "../Icon";

type LegalPageProps = {
  children: ReactNode;
  eyebrow: string;
  title: string;
};

export function LegalPage({ children, eyebrow, title }: LegalPageProps) {
  return (
    <main className="legal-shell">
      <header>
        <Link className="brand" href="/" aria-label="GameWake — início">
          <span className="brand-mark"><Icon name="power" size={19} /></span>
          <span>GameWake</span>
        </Link>
        <Link className="text-link" href="/">Voltar ao início <Icon name="arrow-right" size={16} /></Link>
      </header>
      <article className="legal-document">
        <span className="section-index">{eyebrow}</span>
        <h1>{title}</h1>
        <p className="legal-updated">Última atualização: 3 de agosto de 2026</p>
        {children}
      </article>
      <footer>
        <span>GameWake · Closed beta no Brasil</span>
        <div><Link href="/terms">Termos de Serviço</Link><Link href="/privacy">Política de Privacidade</Link></div>
      </footer>
    </main>
  );
}
