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
        {children}
      </body>
    </html>
  );
}
