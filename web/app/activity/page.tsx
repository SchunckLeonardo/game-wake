import type { Metadata } from "next";
import { DiscordActivityExperience } from "./DiscordActivityExperience";

export const metadata: Metadata = {
  title: "Discord Activity",
  robots: { index: false, follow: false },
};

export default function DiscordActivityPage() {
  return <DiscordActivityExperience />;
}
