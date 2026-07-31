import type { Metadata } from "next";
import { OnboardingFlow } from "./OnboardingFlow";

export const metadata: Metadata = {
  title: "Começar",
  robots: { index: false, follow: false },
};

export default function OnboardingPage() {
  return <OnboardingFlow />;
}
