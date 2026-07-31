import type { Metadata } from "next";
import { ConsoleDashboard } from "../console/ConsoleDashboard";
import { DiscordActivityBridge } from "./DiscordActivityBridge";

export const metadata: Metadata = {
  title: "Discord Activity",
  robots: { index: false, follow: false },
};

export default function DiscordActivityPage() {
  return (
    <>
      <DiscordActivityBridge />
      <ConsoleDashboard accountId="demo" activityMode />
    </>
  );
}
