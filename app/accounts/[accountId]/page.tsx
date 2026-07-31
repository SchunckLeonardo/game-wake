import type { Metadata } from "next";
import { ConsoleDashboard } from "../../console/ConsoleDashboard";

export const metadata: Metadata = {
  title: "Console",
  robots: { index: false, follow: false },
};

export default async function AccountConsole({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <ConsoleDashboard accountId={accountId} />;
}
