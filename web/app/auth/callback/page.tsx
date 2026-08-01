import type { Metadata } from "next";
import { AuthCallback } from "./AuthCallback";

export const metadata: Metadata = {
  title: "Entrando",
  robots: { index: false, follow: false },
};

export default function AuthCallbackPage() {
  return <AuthCallback />;
}
