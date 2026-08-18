import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { headers } from "next/headers";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const designContract = `
THESIS: The World is the shared table; friends, cost, Discord and protection orbit one persistent place instead of a generic SaaS hero or KPI dashboard.
OWN-WORLD: Mist Paper and Night Ink hold the surface; Wake Green acts once, Journey Indigo guides, and a hand-painted circular World carries the visual memory.
STORY: A group sees that the World persists, understands the wake and sleep cycle, trusts the price and backup, then enters with Discord or operates the selected World.
FIRST VIEWPORT: A slim navigation leads to one central World surrounded by four functional stations; the primary Discord action sits on the World itself.
FORM: Mesa Central do World, selected from the surface study; seed keys b35ef383 and 7a7d4a99.
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, and DESIGN.md
`.trim();

export async function generateMetadata(): Promise<Metadata> {
  const requestHeaders = await headers();
  const forwardedHost = requestHeaders.get("x-forwarded-host")?.split(",")[0].trim();
  const requestHost = forwardedHost ?? requestHeaders.get("host");
  const configuredOrigin = process.env.NEXT_PUBLIC_SITE_URL;
  const host = requestHost?.match(/^[a-z0-9.:[\]-]+$/i) ? requestHost : null;
  const forwardedProtocol = requestHeaders
    .get("x-forwarded-proto")
    ?.split(",")[0]
    .trim();
  const protocol =
    forwardedProtocol === "http" || forwardedProtocol === "https"
      ? forwardedProtocol
      : host?.startsWith("localhost")
        ? "http"
        : "https";
  const origin = host
    ? `${protocol}://${host}`
    : (configuredOrigin ?? "https://gamewake.com.br");
  const socialImage = new URL("/og.png", origin).toString();
  const description =
    "Mundos persistentes para jogar com seus amigos, sem manter uma máquina ligada.";

  return {
    metadataBase: new URL(origin),
    title: {
      default: "GameWake | Jogue quando quiser",
      template: "GameWake | %s",
    },
    description,
    icons: {
      icon: [
        { url: "/favicon.ico?v=20260818", sizes: "32x32", type: "image/x-icon" },
        { url: "/icon.svg?v=20260818", type: "image/svg+xml" },
      ],
      shortcut: "/favicon.ico?v=20260818",
    },
    openGraph: {
      type: "website",
      locale: "pt_BR",
      siteName: "GameWake",
      title: "GameWake | Jogue quando quiser",
      description,
      images: [{ url: socialImage, width: 1731, height: 909, alt: "GameWake" }],
    },
    twitter: {
      card: "summary_large_image",
      title: "GameWake | Jogue quando quiser",
      description,
      images: [socialImage],
    },
  };
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR">
      <body className={`${geistSans.variable} ${geistMono.variable}`}>
        <script
          data-design-contract="gamewake-world-table"
          dangerouslySetInnerHTML={{
            __html: `document.currentScript?.before(document.createComment(${JSON.stringify(designContract)}));`,
          }}
        />
        {children}
      </body>
    </html>
  );
}
