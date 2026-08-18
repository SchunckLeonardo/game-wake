import type { Metadata } from "next";
import { ConsoleDashboard } from "../../console/ConsoleDashboard";

export const metadata: Metadata = {
  title: "Console",
  robots: { index: false, follow: false },
};

export default async function AccountConsole({
  params,
  searchParams,
}: {
  params: Promise<{ accountId: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { accountId } = await params;
  const query = await searchParams;
  const sectionValue = Array.isArray(query.section) ? query.section[0] : query.section;
  const initialSection = [
    "worlds",
    "wallet",
    "members",
    "configuration",
    "backups",
    "activity",
  ].includes(sectionValue ?? "")
    ? sectionValue as "worlds" | "wallet" | "members" | "configuration" | "backups" | "activity"
    : "worlds";
  const worldValue = Array.isArray(query.world) ? query.world[0] : query.world;
  return (
    <ConsoleDashboard
      accountId={accountId}
      initialSection={initialSection}
      initialWorldId={worldValue}
    />
  );
}
