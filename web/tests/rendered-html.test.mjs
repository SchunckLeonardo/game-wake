import assert from "node:assert/strict";
import test from "node:test";

async function render(path = "/", environment = {}) {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}-${path}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request(`http://localhost${path}`, {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
      ...environment,
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

test("redirects the site Discord login route to the GameWake API", async () => {
  const previousApiUrl = process.env.GAMEWAKE_API_URL;
  process.env.GAMEWAKE_API_URL = "https://api.gamewake.example/";
  try {
    const response = await render("/auth/discord/start?install=1&accountId=account-1");
    assert.equal(response.status, 307);
    assert.equal(
      response.headers.get("location"),
      "https://api.gamewake.example/auth/discord/start?install=1&accountId=account-1",
    );
  } finally {
    if (previousApiUrl === undefined) delete process.env.GAMEWAKE_API_URL;
    else process.env.GAMEWAKE_API_URL = previousApiUrl;
  }
});

test("renders the public GameWake landing page without starter artifacts", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /<html lang="pt-BR"/i);
  assert.match(html, /<title>GameWake \| Jogue quando quiser/i);
  assert.match(html, /Seu mundo fica\./);
  assert.match(html, /A infraestrutura só acorda quando vocês vão jogar\./);
  assert.match(html, /Entrar com Discord/);
  assert.match(html, /href="\/terms"[^>]*>Termos de Serviço/);
  assert.match(html, /href="\/privacy"[^>]*>Política de Privacidade/);
  assert.match(html, /Pague pelo tempo de jogo, não por uma máquina parada\./);
  assert.match(
    html,
    /<meta property="og:image" content="https:\/\/gamewake\.com\.br\/og\.png"/i,
  );
  assert.match(
    html,
    /<link rel="(?:shortcut )?icon" href="(?:https:\/\/[^"/]+)?\/icon\.svg"/i,
  );
  assert.doesNotMatch(html, /codex-preview|SkeletonPreview|react-loading-skeleton/i);
});

test("renders Terms and Privacy as public, navigable documents", async () => {
  const terms = await render("/terms");
  const privacy = await render("/privacy");

  assert.equal(terms.status, 200);
  assert.match(await terms.text(), /Termos de Serviço/);
  assert.equal(privacy.status, 200);
  const privacyHtml = await privacy.text();
  assert.match(privacyHtml, /Política de Privacidade/);
  assert.match(privacyHtml, /Lei nº 13\.709\/2018/);
});

test("renders the responsive Console with every MVP management surface", async () => {
  const response = await render("/accounts/demo?demo=1");
  assert.equal(response.status, 200);

  const html = await response.text();
  assert.match(html, /Bom jogo, Leonardo/);
  assert.match(html, /Palpagos/);
  assert.match(html, /Acordar World/);
  assert.match(html, /Wallet/);
  assert.match(html, /Membros e Roles/);
  assert.match(html, /Configuração/);
  assert.match(html, /Backups/);
  assert.match(html, /Atividade/);
  assert.doesNotMatch(html, /segredo-do-grupo|203\.0\.113\.10/);
});

test("packages the same Console as a Discord Activity with an auth bridge", async () => {
  const response = await render("/activity");
  assert.equal(response.status, 200);

  const html = await response.text();
  assert.match(html, /data-discord-activity="true"/);
  assert.match(html, /data-activity-auth="waiting"/);
  assert.match(html, /Conectando ao Discord/);
  assert.match(html, /Palpagos/);
});
