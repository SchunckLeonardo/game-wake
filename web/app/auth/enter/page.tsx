import type { Metadata } from "next";
import { AuthEntry } from "./AuthEntry";

export const metadata: Metadata = {
  title: "Entrar",
  robots: { index: false, follow: false },
};

export default function AuthEntryPage() {
  return <AuthEntry />;
}
