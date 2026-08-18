import type { Metadata } from "next";
import { ConsoleDashboard } from "../../../../../console/ConsoleDashboard";

export const metadata: Metadata = {
  title: "Configuração do World",
  robots: { index: false, follow: false },
};

export default async function WorldConfiguration({
  params,
}: {
  params: Promise<{ accountId: string; worldId: string }>;
}) {
  const { accountId, worldId } = await params;
  return (
    <ConsoleDashboard
      accountId={accountId}
      initialSection="configuration"
      initialWorldId={worldId}
    />
  );
}
