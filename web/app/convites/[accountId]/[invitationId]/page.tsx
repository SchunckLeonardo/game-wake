import type { Metadata } from "next";
import { InvitationAcceptance } from "./InvitationAcceptance";

export const metadata: Metadata = {
  title: "Convite",
  robots: { index: false, follow: false },
};

export default async function InvitationPage({
  params,
}: {
  params: Promise<{ accountId: string; invitationId: string }>;
}) {
  const { accountId, invitationId } = await params;
  return <InvitationAcceptance accountId={accountId} invitationId={invitationId} />;
}
