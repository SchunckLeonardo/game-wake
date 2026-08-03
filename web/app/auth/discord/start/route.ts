import { NextResponse } from "next/server";

function apiOrigin(request: Request) {
  const configured =
    process.env.GAMEWAKE_API_URL ?? process.env.NEXT_PUBLIC_GAMEWAKE_API_URL;
  if (!configured) return null;

  try {
    const origin = new URL(configured);
    const requestOrigin = new URL(request.url).origin;
    const isLocalDevelopment = origin.hostname === "localhost";
    if (
      (origin.protocol !== "https:" && !isLocalDevelopment) ||
      origin.origin === requestOrigin
    ) {
      return null;
    }
    return origin;
  } catch {
    return null;
  }
}

export function GET(request: Request) {
  const origin = apiOrigin(request);
  if (!origin) {
    return NextResponse.json(
      {
        error: {
          code: "oauth_unavailable",
          message: "Login com Discord indisponível.",
        },
      },
      { status: 503 },
    );
  }

  const target = new URL("/auth/discord/start", origin);
  const source = new URL(request.url);
  for (const key of ["install", "accountId"]) {
    const value = source.searchParams.get(key);
    if (value) target.searchParams.set(key, value);
  }
  return NextResponse.redirect(target, 307);
}
