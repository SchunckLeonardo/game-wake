import { expect, test } from "@playwright/test";

const ownerAccess = {
  roles: ["owner"],
  permissions: [
    "world:create", "world:view", "world:wake", "world:sleep_when_empty",
    "world:edit", "world:restart", "world:update", "world:force_sleep",
    "world:logs:view", "backup:create", "backup:restore", "membership:manage",
    "role:manage", "integration:manage", "wallet:manage", "world:budget:manage",
    "world:migrate", "world:export", "world:delete", "account:ownership:transfer",
    "account:delete",
  ],
};

function navigation(page: import("@playwright/test").Page, section: string) {
  return page.locator(`[data-testid="nav-${section}"]:visible`);
}

function visibleAccessRole(page: import("@playwright/test").Page) {
  return page.locator(".sidebar-foot:visible, .topbar-section-title small:visible");
}

async function expectControlsSeparated(
  first: import("@playwright/test").Locator,
  second: import("@playwright/test").Locator,
) {
  const firstBox = await first.boundingBox();
  const secondBox = await second.boundingBox();
  expect(firstBox).not.toBeNull();
  expect(secondBox).not.toBeNull();
  const horizontalGap = Math.max(
    (secondBox?.x ?? 0) - ((firstBox?.x ?? 0) + (firstBox?.width ?? 0)),
    (firstBox?.x ?? 0) - ((secondBox?.x ?? 0) + (secondBox?.width ?? 0)),
    0,
  );
  const verticalGap = Math.max(
    (secondBox?.y ?? 0) - ((firstBox?.y ?? 0) + (firstBox?.height ?? 0)),
    (firstBox?.y ?? 0) - ((secondBox?.y ?? 0) + (secondBox?.height ?? 0)),
    0,
  );
  expect(Math.max(horizontalGap, verticalGap)).toBeGreaterThanOrEqual(8);
}

test("landing communicates the product and starts Discord onboarding", async ({
  page,
}) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: /Seu mundo fica/ })).toBeVisible();
  const signIn = page.getByRole("link", { name: "Entrar com Discord" }).first();
  await expect(signIn).toHaveAttribute(
    "href",
    "/auth/enter",
  );
  await expect(page.getByText("Pague pelo tempo de jogo")).toBeVisible();
  await expect(page.getByRole("link", { name: "Termos de Serviço" })).toHaveAttribute("href", "/terms");
  await expect(page.getByRole("link", { name: "Política de Privacidade" })).toHaveAttribute("href", "/privacy");
});

test("returning visitor enters the Console with the persisted session without reopening OAuth", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("gamewake_session", "persisted-session"));
  await page.route("**/api/v1/me/accounts", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ accounts: [{ id: "account-returning", name: "Grupo salvo", access: ownerAccess }] }),
  }));

  await page.goto("/");
  await page.getByRole("link", { name: "Entrar com Discord" }).first().click();

  await expect(page).toHaveURL(/\/accounts\/account-returning$/);
});

test("returning visitor reopens the last Account and World they selected", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("gamewake_session", "persisted-session");
    localStorage.setItem("gamewake:last-account", "account-last");
    localStorage.setItem("gamewake:last-world:account-last", "world-last");
  });
  await page.route("**/api/v1/me/accounts", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({
      accounts: [
        { id: "account-first", name: "Primeiro grupo", access: ownerAccess },
        { id: "account-last", name: "Grupo lembrado", access: ownerAccess },
      ],
    }),
  }));
  await page.route("**/api/v1/accounts/account-last/worlds", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({
      worlds: [
        { id: "world-first", name: "Primeiro World", region: "sa-east-1", status: "sleeping" },
        { id: "world-last", name: "World lembrado", region: "sa-east-1", status: "sleeping" },
      ],
    }),
  }));
  await page.route("**/api/v1/accounts/account-last/wallet", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ wallet: { balance: "25.00", availableBalance: "25.00", statement: [] } }),
  }));

  await page.goto("/auth/enter");

  await expect(page).toHaveURL(/\/accounts\/account-last$/);
  await expect(page.getByRole("heading", { name: "World lembrado" })).toBeVisible();
});

test("Console switches among existing groups without OAuth and offers installing a new server", async ({ page }) => {
  let releaseSecondAccountWorlds: (() => void) | undefined;
  const secondAccountWorldsReady = new Promise<void>((resolve) => {
    releaseSecondAccountWorlds = resolve;
  });
  let secondAccountWorldRequests = 0;
  await page.addInitScript(() => localStorage.setItem("gamewake_session", "signed-session"));
  await page.route("**/api/v1/me/accounts", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({
      accounts: [
        { id: "account-one", name: "Servidor Um", discordGuildId: "111", access: ownerAccess },
        { id: "account-two", name: "Servidor Dois", discordGuildId: "222", access: ownerAccess },
      ],
    }),
  }));
  for (const [account, world] of [["account-one", "World Um"], ["account-two", "World Dois"]]) {
    await page.route(`**/api/v1/accounts/${account}/worlds`, async (route) => {
      if (account === "account-two") {
        secondAccountWorldRequests += 1;
        await secondAccountWorldsReady;
      }
      return route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ worlds: [{ id: `world-${account}`, name: world, region: "sa-east-1", status: "sleeping" }] }),
      });
    });
    await page.route(`**/api/v1/accounts/${account}/wallet`, (route) => route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ wallet: { balance: "25.00", availableBalance: "25.00", statement: [] } }),
    }));
  }

  await page.goto("/accounts/account-one");
  await page.getByRole("button", { name: "Trocar grupo ou servidor" }).first().click();
  const switcher = page.getByRole("dialog", { name: "Escolher grupo ou servidor" });
  await expect(switcher.getByTestId("account-switcher-skeleton")).toBeVisible();
  await expect(switcher.getByRole("status")).toHaveText("Buscando seus grupos e Worlds…");
  await page.getByRole("button", { name: "Fechar troca de grupo" }).click();
  await page.getByRole("button", { name: "Trocar grupo ou servidor" }).first().click();
  await expect(switcher.getByTestId("account-switcher-skeleton")).toBeVisible();
  expect(secondAccountWorldRequests).toBe(1);
  releaseSecondAccountWorlds?.();
  await expect(page.getByRole("dialog", { name: "Escolher grupo ou servidor" })).toContainText("World Dois");
  await expect(switcher.getByTestId("account-switcher-skeleton")).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Adicionar GameWake a outro servidor" })).toHaveAttribute(
    "href",
    "/auth/discord/start?install=1",
  );
  await page.getByRole("button", { name: "Fechar troca de grupo" }).click();
  await page.getByRole("button", { name: "Trocar grupo ou servidor" }).first().click();
  await expect(switcher).toContainText("World Dois");
  expect(secondAccountWorldRequests).toBe(1);
  await page.getByRole("link", { name: /Servidor Dois/ }).click();

  await expect(page).toHaveURL(/\/accounts\/account-two$/);
  await expect(page.getByRole("heading", { name: "World Dois" })).toBeVisible();
});

test("logout is an explicit confirmed action in the user menu", async ({ page }) => {
  await page.addInitScript(() => {
    if (sessionStorage.getItem("gamewake:test-session-seeded")) return;
    localStorage.setItem("gamewake_session", "signed-session");
    sessionStorage.setItem("gamewake:test-session-seeded", "true");
  });
  await page.route("**/api/v1/me/accounts", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ accounts: [{ id: "account-live", name: "Grupo", access: ownerAccess }] }),
  }));
  await page.route("**/api/v1/accounts/account-live/worlds", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ worlds: [] }),
  }));
  await page.route("**/api/v1/accounts/account-live/wallet", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ wallet: { availableBalance: "0.00", statement: [] } }),
  }));

  await page.goto("/accounts/account-live");
  await page.getByRole("button", { name: "Abrir menu do usuário" }).click();
  await page.getByRole("button", { name: "Sair do GameWake" }).click();
  await expect(page.getByText("Sair desta sessão?")).toBeVisible();
  await page.getByRole("button", { name: "Confirmar saída" }).click();

  await expect(page).toHaveURL(/\/$/);
  expect(await page.evaluate(() => localStorage.getItem("gamewake_session"))).toBeNull();
});

test("group completes onboarding without infrastructure vocabulary", async ({ page }) => {
  await page.goto("/onboarding?demo=1");
  await expect(page.getByTestId("onboarding")).toHaveAttribute("data-hydrated", "true");

  await page.getByLabel("Nome do grupo").fill("Sexta com os amigos");
  await page.getByRole("button", { name: "Continuar" }).click();
  await page.getByLabel("Nome do World").fill("Palpagos");
  await page.getByRole("button", { name: "Criar meu World" }).click();

  await expect(page.getByText("Tudo pronto para jogar")).toBeVisible();
  await expect(page.getByText(/EC2|Aurora|subnet|instance type/i)).toHaveCount(0);
});

test("group contributes, invites friends, wakes, connects, configures and sleeps", async ({
  page,
}) => {
  await page.goto("/accounts/demo?demo=1");
  await expect(page.getByTestId("console")).toHaveAttribute("data-hydrated", "true");

  await navigation(page, "wallet").click();
  await page.getByRole("button", { name: "R$ 50" }).click();
  await expect(page.getByTestId("create-checkout")).toHaveText("Contribuir R$ 50,00");
  await page.getByLabel("Limite mensal do World").fill("100");
  await page.getByRole("button", { name: "Salvar orçamento" }).click();
  await expect(page.getByRole("button", { name: "Orçamento salvo ✓" })).toBeVisible();

  await navigation(page, "members").click();
  await page.getByTestId("create-invitation-link").click();
  await expect(page.getByLabel("Link de convite criado")).toBeVisible();
  await expect(page.getByText("Caio")).toBeVisible();

  await navigation(page, "worlds").click();
  await page.getByTestId("wake-world").click();
  await expect(page.getByRole("dialog", { name: "Confirmar despertar de Palpagos" })).toContainText("R$ 2,49 por hora");
  await page.getByRole("button", { name: "Reservar R$ 1,04 e acordar" }).click();
  const preparation = page.getByRole("status");
  await expect(preparation).toContainText("Preparando a máquina do jogo");
  await expect(preparation).toContainText("restaurando seu World protegido");
  await expect(preparation).toContainText("Etapa 3 de 7");
  await expect(preparation.getByRole("list", { name: "Etapas do despertar" })).toContainText(
    "Confirmando que está pronto",
  );
  await expect(preparation.locator(".meter")).toHaveCount(0);
  await expect(page.getByTestId("connect-world")).toBeVisible();
  await page.getByTestId("connect-world").click();
  await expect(page.getByRole("dialog", { name: "Conectar ao Palpagos" })).toBeVisible();
  await page.getByRole("button", { name: "Fechar conexão" }).click();

  await navigation(page, "configuration").click();
  await page.getByLabel("Drop de itens dos inimigos").fill("4.0");
  await page.getByTestId("save-configuration").click();
  await expect(page.getByTestId("save-configuration")).toHaveText(
    "Configuração salva ✓",
  );

  await navigation(page, "worlds").click();
  await page.getByTestId("sleep-world").click();
  await expect(page.getByTestId("wake-world")).toContainText("Acordar World");
});

test("Discord Activity uses the same safe Console", async ({ page }) => {
  await page.goto("/activity");
  await expect(page.locator("[data-discord-activity='true']")).toBeVisible();
  await expect(page.getByText("Palpagos")).toBeVisible();
  await expect(page.getByText("segredo-do-grupo")).toHaveCount(0);
});

test("OAuth callback persists the session and selected Discord server", async ({
  page,
}) => {
  await page.route("**/api/v1/me/accounts", async (route) => {
    expect(route.request().headers().authorization).toBe("Bearer signed-session");
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        accounts: [{ id: "account-live", name: "Grupo real", discordGuildId: null, access: ownerAccess }],
      }),
    });
  });

  await page.goto(
    "/auth/callback#session=signed-session&discordGuildId=123456789012345678&accountId=account-live",
  );

  await expect(page).toHaveURL(/\/accounts\/account-live$/);
  expect(await page.evaluate(() => localStorage.getItem("gamewake_session"))).toBe(
    "signed-session",
  );
  expect(
    await page.evaluate(() => localStorage.getItem("gamewake_discord_guild_id")),
  ).toBe("123456789012345678");
  expect(await page.evaluate(() => localStorage.getItem("gamewake_known_user"))).toBe("true");
});

test("OAuth reauthentication returns to the exact Console section", async ({ page }) => {
  await page.addInitScript(() => {
    if (!sessionStorage.getItem("gamewake:test-post-auth-seeded")) {
      localStorage.setItem(
        "gamewake:post-auth-return",
        "/accounts/account-live?section=members&world=world-live",
      );
      sessionStorage.setItem("gamewake:test-post-auth-seeded", "true");
    }
  });
  await page.route("**/api/v1/me/accounts", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({
      accounts: [{ id: "account-live", name: "Grupo real", access: ownerAccess }],
    }),
  }));

  await page.goto(
    "/auth/callback#session=renewed-session&accountId=account-live&reauthenticated=1",
  );

  await expect(page).toHaveURL(
    /\/accounts\/account-live\?section=members&world=world-live$/,
  );
  expect(
    await page.evaluate(() => localStorage.getItem("gamewake:post-auth-return")),
  ).toBeNull();
});

test("selecting another Discord server loads only that server account", async ({ page }) => {
  let oldAccountWorldsRequested = false;
  await page.addInitScript(() => {
    localStorage.setItem("gamewake_session", "old-session");
    localStorage.setItem("gamewake_discord_guild_id", "123456789012345678");
  });
  await page.route("**/api/v1/me/accounts", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({
      accounts: [
        { id: "account-old", name: "Servidor antigo", discordGuildId: "123456789012345678", access: ownerAccess },
        { id: "account-new", name: "Servidor novo", discordGuildId: "987654321098765432", access: ownerAccess },
      ],
    }),
  }));
  await page.route("**/api/v1/accounts/account-old/worlds", (route) => {
    oldAccountWorldsRequested = true;
    return route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ worlds: [{ id: "world-old", name: "World antigo" }] }),
    });
  });
  await page.route("**/api/v1/accounts/account-new/worlds", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ worlds: [] }),
  }));
  await page.route("**/api/v1/accounts/account-new/wallet", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ wallet: { availableBalance: "0.00", statement: [] } }),
  }));

  await page.goto(
    "/auth/callback#session=new-session&discordGuildId=987654321098765432&accountId=account-new",
  );

  await expect(page).toHaveURL(/\/accounts\/account-new$/);
  await expect(page.getByTestId("empty-world-state")).toBeVisible();
  await expect(page.getByText("World antigo")).toHaveCount(0);
  expect(oldAccountWorldsRequested).toBe(false);
});

test("selecting a new Discord server starts a separate group instead of showing old Worlds", async ({
  page,
}) => {
  await page.route("**/api/v1/me/accounts", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({
      accounts: [
        { id: "account-old", name: "Servidor antigo", discordGuildId: "123456789012345678", access: ownerAccess },
      ],
    }),
  }));

  await page.goto(
    "/auth/callback#session=new-session&discordGuildId=987654321098765432",
  );

  await expect(page).toHaveURL(/\/onboarding$/);
});

test("OAuth callback makes one-time Owner recovery codes impossible to miss", async ({
  page,
}) => {
  const recovery = Buffer.from(JSON.stringify([
    {
      accountId: "account-live",
      verifiedEmail: "owner@example.com",
      codes: ["RECOVERY-ONE", "RECOVERY-TWO"],
    },
  ])).toString("base64url");
  await page.route("**/api/v1/me/accounts", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ accounts: [{ id: "account-live", access: ownerAccess }] }),
  }));

  await page.goto(`/auth/callback#session=signed-session&ownerRecovery=${recovery}`);

  await expect(page.getByRole("heading", { name: "Guarde seus códigos de recuperação" })).toBeVisible();
  await expect(page.getByText("RECOVERY-ONE")).toBeVisible();
  await page.getByRole("button", { name: "Já guardei, continuar" }).click();
  await expect(page).toHaveURL(/\/accounts\/account-live$/);
});

test("authenticated onboarding creates a real account and Palworld through the API", async ({
  page,
}) => {
  let accountBody: unknown;
  let worldBody: unknown;
  await page.addInitScript(() => {
    localStorage.setItem("gamewake_session", "signed-session");
    localStorage.setItem("gamewake_discord_guild_id", "123456789012345678");
  });
  await page.route("**/api/v1/accounts", async (route) => {
    accountBody = route.request().postDataJSON();
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify({ account: { id: "account-new", name: "Grupo novo" } }),
    });
  });
  await page.route("**/api/v1/accounts/account-new/worlds", async (route) => {
    worldBody = route.request().postDataJSON();
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify({ world: { id: "world-new", name: "Novo mundo" } }),
    });
  });

  await page.goto("/onboarding");
  await page.getByLabel("Nome do grupo").fill("Grupo novo");
  await page.getByRole("button", { name: "Continuar" }).click();
  await page.getByLabel("Nome do World").fill("Novo mundo");
  await page.getByRole("button", { name: "Criar meu World" }).click();

  await expect(page.getByText("Tudo pronto para jogar")).toBeVisible();
  await expect(page.getByRole("link", { name: "Abrir Console" })).toHaveAttribute(
    "href",
    "/accounts/account-new",
  );
  expect(accountBody).toEqual({
    name: "Grupo novo",
    discordGuildId: "123456789012345678",
  });
  expect(
    await page.evaluate(() => localStorage.getItem("gamewake_discord_guild_id")),
  ).toBeNull();
  expect(worldBody).toMatchObject({
    name: "Novo mundo",
    gameTemplateId: "palworld:1",
    region: "sa-east-1",
    runtimeProfileId: "palworld-small",
  });
});

test("authenticated Console loads and mutates the real World through bearer API", async ({
  page,
}) => {
  let worldStatus = "sleeping";
  let wakeBody: unknown;
  await page.addInitScript(() => localStorage.setItem("gamewake_session", "signed-session"));
  await page.route("**/api/v1/me/accounts", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        accounts: [{ id: "account-live", name: "Grupo real", discordGuildId: null, access: ownerAccess }],
      }),
    });
  });
  await page.route("**/api/v1/accounts/account-live/worlds", async (route) => {
    expect(route.request().headers().authorization).toBe("Bearer signed-session");
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        worlds: [
          {
            id: "world-live",
            accountId: "account-live",
            name: "Mundo real",
            gameTemplateId: "palworld:1",
            region: "sa-east-1",
            runtimeProfileId: "palworld-small",
            status: worldStatus,
          },
        ],
      }),
    });
  });
  await page.route("**/api/v1/accounts/account-live/wallet", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        wallet: {
          accountId: "account-live",
          currency: "BRL",
          balance: "20.00",
          availableBalance: "18.50",
          statement: [],
        },
      }),
    });
  });
  await page.route("**/api/v1/accounts/account-live/worlds/world-live/wake", async (route) => {
    wakeBody = route.request().postDataJSON();
    worldStatus = "waking";
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({ operation: { id: "operation-live", type: "wake", status: "running", phase: "restoring_world", createdAt: "2026-07-31T20:00:00Z" } }),
    });
  });
  await page.route("**/api/v1/accounts/account-live/worlds/world-live/operations", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ operations: [{ id: "operation-live", type: "wake", status: "running", phase: "restoring_world", createdAt: "2026-07-31T20:00:00Z" }] }),
  }));
  await page.route("**/api/v1/accounts/account-live/worlds/world-live/wake/estimate", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ estimate: { currency: "BRL", hourlyRate: "2.49", minimumReservation: "1.04", reservedMinutes: 25 } }),
    });
  });

  await page.goto("/accounts/account-live");
  await expect(page.getByRole("button", { name: "Trocar grupo ou servidor" }).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "Mundo real" })).toBeVisible();
  await expect(page.getByText("R$ 18,50").first()).toBeVisible();
  await expect(page.getByText("R$ 1,50 reservados temporariamente")).toBeVisible();
  await page.getByTestId("wake-world").click();
  const wakeDialog = page.getByRole("dialog", { name: "Confirmar despertar de Mundo real" });
  await expect(wakeDialog).toContainText("R$ 2,49 por hora");
  await expect(wakeDialog).toContainText("R$ 1,04 reservados agora");
  await expect(wakeDialog).toContainText("não é uma cobrança");
  await page.getByRole("button", { name: "Reservar R$ 1,04 e acordar" }).click();

  expect(wakeBody).toMatchObject({ idempotencyKey: expect.any(String) });
  const preparation = page.getByRole("status");
  await expect(preparation).toContainText("Preparando a máquina do jogo");
  await expect(preparation).toContainText("restaurando seu World protegido");
  await expect(preparation).toContainText("Etapa 3 de 7");
  await expect(preparation.getByRole("list", { name: "Etapas do despertar" })).toContainText(
    "Confirmando que está pronto",
  );
  await expect(preparation.locator(".meter")).toHaveCount(0);

  worldStatus = "needs_attention";
  await expect(page.getByTestId("wake-world")).toContainText("Tentar novamente", {
    timeout: 6_000,
  });
  await expect(page.getByTestId("wake-world")).toBeEnabled();
});

test("Manager chooses a fixed World password or a new random password for every wake", async ({ page }) => {
  let passwordBody: unknown;
  let schemaRequests = 0;
  await page.addInitScript(() => localStorage.setItem("gamewake_session", "signed-session"));
  await page.route("**/api/v1/me/accounts", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ accounts: [{ id: "account-live", name: "Grupo", access: ownerAccess }] }),
  }));
  await page.route("**/api/v1/accounts/account-live/worlds", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ worlds: [{ id: "world-live", name: "Mundo real", gameTemplateId: "palworld:1", region: "sa-east-1", status: "sleeping" }] }),
  }));
  await page.route("**/api/v1/accounts/account-live/wallet", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ wallet: { balance: "25.00", availableBalance: "25.00", statement: [] } }),
  }));
  await page.route("**/api/v1/accounts/account-live/worlds/world-live/configuration/schema", (route) => {
    schemaRequests += 1;
    return route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ template: { id: "palworld:1", configurationFields: [{
        key: "enemy_drop_item_rate",
        label: "Drop de itens dos inimigos",
        valueType: "number",
        default: 1,
        acceptedValues: "maior que 0",
        impact: "Multiplica os drops.",
        officialDocumentationUrl: "https://tech.palworldgame.com/settings-and-operation/configuration/",
      }] } }),
    });
  });
  await page.route("**/api/v1/accounts/account-live/worlds/world-live/configuration", async (route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({ revision: { values: { enemy_drop_item_rate: 1 } } }),
      });
    }
    return route.fulfill({ contentType: "application/json", body: JSON.stringify({}) });
  });
  await page.route("**/api/v1/accounts/account-live/worlds/world-live/access/password", async (route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({ password: { mode: "fixed" } }),
      });
    }
    passwordBody = route.request().postDataJSON();
    return route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ password: { mode: "random_each_run" } }),
    });
  });

  await page.goto("/accounts/account-live");
  await navigation(page, "configuration").click();
  await expectControlsSeparated(
    page.locator(".password-mode-options > label").nth(1),
    page.getByTestId("save-configuration"),
  );
  await page.getByLabel("Gerar uma senha nova a cada despertar").check();
  await expect(page.getByText(/senha muda somente quando uma nova sessão começa/i)).toBeVisible();
  await page.getByTestId("save-configuration").click();

  await expect.poll(() => passwordBody).toEqual({ mode: "random_each_run" });
  await expect(page.getByTestId("save-configuration")).toHaveText("Configuração salva ✓");
  const schemaRequestsBeforeReopen = schemaRequests;
  await navigation(page, "worlds").click();
  await navigation(page, "configuration").click();
  await expect(page.getByLabel("Drop de itens dos inimigos")).toBeVisible();
  expect(schemaRequests).toBe(schemaRequestsBeforeReopen);
});

test("Console keeps following a World startup when an auxiliary request fails", async ({ page }) => {
  let worldRequests = 0;
  let accountRequests = 0;
  let walletRequests = 0;
  let operationRequests = 0;
  await page.addInitScript(() => localStorage.setItem("gamewake_session", "signed-session"));
  await page.route("**/api/v1/me/accounts", (route) => {
    accountRequests += 1;
    return route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        accounts: [{
          id: "account-starting",
          name: "Grupo iniciando",
          access: {
            roles: ["owner"],
            permissions: ["world:view", "world:wake"],
          },
        }],
      }),
    });
  });
  await page.route("**/api/v1/accounts/account-starting/worlds", (route) => {
    worldRequests += 1;
    const status = worldRequests >= 2 ? "online" : "waking";
    return route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        worlds: [{
          id: "world-starting",
          name: "Mundo iniciando",
          region: "sa-east-1",
          status,
          permissions: ["world:view", "world:wake"],
          connection: status === "online" ? { host: "203.0.113.15", port: 8211 } : null,
        }],
      }),
    });
  });
  await page.route("**/api/v1/accounts/account-starting/wallet", (route) => {
    walletRequests += 1;
    return route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ error: { code: "temporarily_unavailable" } }),
    });
  });
  await page.route("**/api/v1/accounts/account-starting/worlds/world-starting/operations", (route) => {
    operationRequests += 1;
    return route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        operations: [{
          id: "operation-starting",
          type: "wake",
          status: worldRequests >= 2 ? "succeeded" : "running",
          phase: worldRequests >= 2 ? "complete" : "restoring_world",
          createdAt: "2026-08-10T12:00:00Z",
        }],
      }),
    });
  });

  await page.goto("/accounts/account-starting");

  await expect(page.getByRole("status")).toContainText("Preparando a máquina do jogo");
  await expect(page.getByTestId("connect-world")).toBeVisible({ timeout: 7_000 });
  await expect(page.getByText(/progresso do World está atualizado.*dados auxiliares/i)).toBeVisible();
  expect(accountRequests).toBe(1);
  expect(walletRequests).toBe(1);
  expect(worldRequests).toBeGreaterThanOrEqual(2);
  expect(operationRequests).toBeGreaterThanOrEqual(1);
});

test("World polling pauses in a hidden tab and revalidates when it becomes visible", async ({ page }) => {
  let worldRequests = 0;
  await page.addInitScript(() => {
    localStorage.setItem("gamewake_session", "signed-session");
    Object.defineProperty(document, "hidden", {
      configurable: true,
      get: () => (window as typeof window & { __gamewakeHidden?: boolean }).__gamewakeHidden ?? false,
    });
  });
  await page.route("**/api/v1/me/accounts", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({
      accounts: [{ id: "account-hidden", name: "Grupo", access: ownerAccess }],
    }),
  }));
  await page.route("**/api/v1/accounts/account-hidden/worlds", (route) => {
    worldRequests += 1;
    return route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        worlds: [{
          id: "world-hidden",
          name: "World oculto",
          region: "sa-east-1",
          status: "waking",
          permissions: ["world:view", "world:wake"],
        }],
      }),
    });
  });
  await page.route("**/api/v1/accounts/account-hidden/wallet", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ wallet: { balance: "25.00", availableBalance: "25.00", statement: [] } }),
  }));
  await page.route("**/api/v1/accounts/account-hidden/worlds/world-hidden/operations", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ operations: [] }),
  }));

  await page.goto("/accounts/account-hidden");
  await expect(page.getByRole("heading", { name: "World oculto" })).toBeVisible();
  await page.evaluate(() => {
    (window as typeof window & { __gamewakeHidden?: boolean }).__gamewakeHidden = true;
    document.dispatchEvent(new Event("visibilitychange"));
  });
  // Let a request that crossed the visibility boundary settle before measuring the paused period.
  await page.waitForTimeout(150);
  const requestsWhileHidden = worldRequests;
  await page.waitForTimeout(3_300);
  expect(worldRequests).toBe(requestsWhileHidden);

  await page.evaluate(() => {
    (window as typeof window & { __gamewakeHidden?: boolean }).__gamewakeHidden = false;
    document.dispatchEvent(new Event("visibilitychange"));
  });
  await expect.poll(() => worldRequests).toBe(requestsWhileHidden + 1);
});

test("Player, Moderador and Owner see the Console allowed by their permissions", async ({ page }) => {
  const profiles = {
    player: {
      roles: ["player"],
      permissions: ["world:view", "world:wake", "world:sleep_when_empty"],
    },
    manager: {
      roles: ["manager"],
      permissions: [
        "world:view", "world:wake", "world:sleep_when_empty", "world:edit",
        "world:restart", "world:update", "world:force_sleep", "world:logs:view",
        "backup:create", "backup:restore",
      ],
    },
    owner: {
      roles: ["owner"],
      permissions: [
        "world:create", "world:view", "world:wake", "world:sleep_when_empty",
        "world:edit", "world:restart", "world:update", "world:force_sleep",
        "world:logs:view", "backup:create", "backup:restore", "membership:manage",
        "role:manage", "integration:manage", "wallet:manage", "world:budget:manage",
        "world:migrate", "world:export", "world:delete", "account:ownership:transfer",
        "account:delete",
      ],
    },
  } as const;
  let profile: keyof typeof profiles = "player";
  await page.addInitScript(() => localStorage.setItem("gamewake_session", "signed-session"));
  await page.route("**/api/v1/me/accounts", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({
      accounts: [{ id: "account-role", name: "Grupo por Role", access: profiles[profile] }],
    }),
  }));
  await page.route("**/api/v1/accounts/account-role/worlds", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({
      worlds: [{
        id: "world-role",
        name: "Mundo por Role",
        region: "sa-east-1",
        status: "sleeping",
        permissions: profiles[profile].permissions,
      }],
    }),
  }));
  await page.route("**/api/v1/accounts/account-role/wallet", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ wallet: { availableBalance: "10.00", statement: [] } }),
  }));
  await page.route("**/api/v1/accounts/account-role/worlds/world-role/operations", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ operations: [] }),
  }));

  await page.goto("/accounts/account-role");
  await expect(visibleAccessRole(page)).toContainText("Player");
  await expect(navigation(page, "members")).toHaveCount(0);
  await expect(navigation(page, "configuration")).toHaveCount(0);
  await expect(navigation(page, "backups")).toHaveCount(0);

  profile = "manager";
  await page.reload();
  await expect(visibleAccessRole(page)).toContainText("Moderador");
  await expect(navigation(page, "members")).toHaveCount(0);
  await expect(navigation(page, "configuration")).toBeVisible();
  await expect(navigation(page, "backups")).toBeVisible();

  profile = "owner";
  await page.reload();
  await expect(visibleAccessRole(page)).toContainText("Owner");
  await expect(navigation(page, "members")).toBeVisible();
  await expect(navigation(page, "configuration")).toBeVisible();
  await expect(navigation(page, "backups")).toBeVisible();
});

test("friend understands and accepts a Console invitation link", async ({ page }) => {
  const accountId = "11111111-1111-4111-8111-111111111111";
  const invitationId = "22222222-2222-4222-8222-222222222222";
  let accepted = false;
  await page.addInitScript(() => localStorage.setItem("gamewake_session", "friend-session"));
  await page.route(`**/api/v1/accounts/${accountId}/invitations/${invitationId}/accept`, (route) => {
    accepted = route.request().method() === "POST";
    return route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ membership: { id: "friend-membership", roles: [{ role: "manager" }] } }),
    });
  });
  await page.route(`**/api/v1/accounts/${accountId}/invitations/${invitationId}`, (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({
      invitation: {
        id: invitationId,
        accountName: "Sexta com os amigos",
        access: "console",
        predefinedRole: "manager",
        customRoleId: null,
        status: "pending",
        expiresAt: "2026-08-17T12:00:00Z",
      },
    }),
  }));
  await page.route("**/api/v1/me/accounts", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({
      accounts: [{
        id: accountId,
        name: "Sexta com os amigos",
        access: { roles: ["manager"], permissions: ["world:view"] },
      }],
    }),
  }));
  await page.route(`**/api/v1/accounts/${accountId}/worlds`, (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ worlds: [] }),
  }));
  await page.route(`**/api/v1/accounts/${accountId}/wallet`, (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ wallet: { availableBalance: "0.00", statement: [] } }),
  }));

  await page.goto(`/convites/${accountId}/${invitationId}`);
  await expect(page.getByRole("heading", { name: "Ajude a gerenciar o grupo" })).toBeVisible();
  await expect(page.getByText(/Sexta com os amigos.*Moderador/)).toBeVisible();
  await expect(page.getByText("Gerenciar somente o que a Role permitir")).toBeVisible();
  await page.getByRole("button", { name: "Aceitar e continuar" }).click();

  await expect.poll(() => accepted).toBe(true);
  await expect(page).toHaveURL(`/accounts/${accountId}`);
});

test("live Console switches Worlds and persists Auto Sleep and World Budget", async ({ page }) => {
  let settingsBody: unknown;
  let budgetBody: unknown;
  await page.addInitScript(() => localStorage.setItem("gamewake_session", "signed-session"));
  await page.route("**/api/v1/me/accounts", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ accounts: [{ id: "account-live", name: "Grupo real", access: ownerAccess }] }),
  }));
  await page.route("**/api/v1/accounts/account-live/wallet", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ wallet: { availableBalance: "30.00", statement: [] } }),
  }));
  await page.route("**/api/v1/accounts/account-live/worlds", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ worlds: [
      { id: "world-one", name: "Palpagos", region: "sa-east-1", status: "sleeping", autoSleepMinutes: 20 },
      { id: "world-two", name: "Ilha Dois", region: "sa-east-1", status: "sleeping", autoSleepMinutes: 30 },
    ] }),
  }));
  await page.route("**/api/v1/accounts/account-live/worlds/world-two/settings", async (route) => {
    settingsBody = route.request().postDataJSON();
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ world: { id: "world-two", name: "Ilha Dois", region: "sa-east-1", status: "sleeping", autoSleepMinutes: 60 } }),
    });
  });
  await page.route("**/api/v1/accounts/account-live/worlds/world-two/budget", async (route) => {
    if (route.request().method() === "PUT") budgetBody = route.request().postDataJSON();
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ budget: { worldId: "world-two", period: "2026-07", monthlyLimit: "90.00", spent: "10.00", reserved: "0.00", committed: "10.00", percentage: "11.11", wakeAllowed: true } }),
    });
  });

  await page.goto("/accounts/account-live");
  await page.getByRole("tab", { name: /Ilha Dois/ }).click();
  await expect(page.getByRole("heading", { name: "Ilha Dois" })).toBeVisible();
  await page.getByLabel("Auto Sleep").selectOption("60");
  await expect.poll(() => settingsBody).toEqual({ autoSleepMinutes: 60 });

  await navigation(page, "wallet").click();
  await page.getByLabel("Limite mensal do World").fill("90.00");
  await page.getByRole("button", { name: "Salvar orçamento" }).click();
  await expect.poll(() => budgetBody).toMatchObject({ monthlyLimit: "90.00", idempotencyKey: expect.any(String) });
});

test("Console dismisses a failed World Budget request after five seconds across navigation", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("gamewake_session", "signed-session"));
  await page.route("**/api/v1/me/accounts", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ accounts: [{ id: "account-live", name: "Grupo real", access: ownerAccess }] }),
  }));
  await page.route("**/api/v1/accounts/account-live/wallet", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ wallet: { availableBalance: "30.00", statement: [] } }),
  }));
  await page.route("**/api/v1/accounts/account-live/worlds", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ worlds: [
      { id: "world-live", name: "Palpagos", region: "sa-east-1", status: "sleeping", autoSleepMinutes: 20 },
    ] }),
  }));
  await page.route("**/api/v1/accounts/account-live/worlds/world-live/budget", async (route) => {
    if (route.request().method() === "PUT") {
      await route.abort("failed");
      return;
    }
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ budget: null }),
    });
  });

  await page.goto("/accounts/account-live");
  await navigation(page, "wallet").click();
  await page.getByLabel("Limite mensal do World").fill("90.00");
  await page.getByRole("button", { name: "Salvar orçamento" }).click();

  const alert = page.getByRole("alert");
  await expect(alert).toContainText("Não foi possível conectar ao GameWake");
  await navigation(page, "worlds").click();
  await expect(alert).toBeHidden({ timeout: 6_000 });
});

test("Discord-bootstrapped account creates its first World from the Console", async ({
  page,
}) => {
  let createdWorldBody: unknown;
  await page.addInitScript(() => localStorage.setItem("gamewake_session", "signed-session"));
  await page.route("**/api/v1/me/accounts", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ accounts: [{ id: "account-empty", name: "Grupo do Discord", access: ownerAccess }] }),
  }));
  await page.route("**/api/v1/accounts/account-empty/wallet", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ wallet: { availableBalance: "0.00", statement: [] } }),
  }));
  await page.route("**/api/v1/accounts/account-empty/worlds", (route) => {
    if (route.request().method() === "POST") {
      createdWorldBody = route.request().postDataJSON();
      return route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({ world: { id: "world-first", name: "Primeiro World", region: "sa-east-1", status: "sleeping" } }),
      });
    }
    return route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ worlds: [] }),
    });
  });

  await page.goto("/accounts/account-empty");
  await expect(page.getByRole("heading", { name: "Seu grupo ainda não tem um World" })).toBeVisible();
  await expect(page.getByText("Crie o World antes de tentar acordá-lo")).toBeVisible();
  await expect(page.getByTestId("wake-world")).toHaveCount(0);
  await page.getByRole("button", { name: "Criar meu primeiro World" }).click();
  await page.getByLabel("Nome do novo World").fill("Primeiro World");
  await expectControlsSeparated(
    page.getByLabel("Nome do novo World"),
    page.getByRole("button", { name: "Criar World" }),
  );
  await page.getByRole("button", { name: "Criar World" }).click();

  await expect(page.getByRole("heading", { name: "Primeiro World" })).toBeVisible();
  const guide = page.getByTestId("first-session-guide");
  await expect(guide).toBeVisible();
  await expect(guide).toContainText("World criado");
  await expect(guide).toContainText("Adicionar créditos");
  await expect(guide).toContainText("Acordar o World");
  await expect(guide).toContainText("Conectar e jogar");
  await expect(guide).toContainText("Pelo Console");
  await expect(guide).toContainText("Pelo Discord");
  await expect(guide).toContainText("/gamewake acordar");
  await expect(guide).toContainText("/gamewake conectar");
  await expect(guide).toContainText("/gamewake convidar @amigo1 @amigo2");
  await expect(guide).toContainText("/gamewake aceitar");
  expect(createdWorldBody).toMatchObject({
    name: "Primeiro World",
    gameTemplateId: "palworld:1",
    region: "sa-east-1",
    runtimeProfileId: "palworld-small",
  });
});

test("returning from a paid Pix reconciles and refreshes the Wallet", async ({ page }) => {
  let reconciled = false;
  await page.addInitScript(() => localStorage.setItem("gamewake_session", "signed-session"));
  await page.route("**/api/v1/me/accounts", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ accounts: [{ id: "account-paid", name: "Grupo pago", access: ownerAccess }] }),
  }));
  await page.route("**/api/v1/accounts/account-paid/worlds", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ worlds: [] }),
  }));
  await page.route("**/api/v1/accounts/account-paid/wallet", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({
      wallet: { availableBalance: reconciled ? "25.00" : "0.00", statement: [] },
    }),
  }));
  await page.route(
    "**/api/v1/accounts/account-paid/wallet/contributions/contribution-paid/reconcile",
    (route) => {
      expect(route.request().method()).toBe("POST");
      reconciled = true;
      return route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({ contribution: { id: "contribution-paid", status: "completed" } }),
      });
    },
  );

  await page.goto(
    "/accounts/account-paid?payment=complete&contributionId=contribution-paid",
  );

  await expect(page.getByTestId("wallet-panel")).toBeVisible();
  await expect(page.getByRole("status")).toContainText(
    "Pagamento confirmado. Seus créditos já estão disponíveis.",
  );
  await expect(page.getByText("R$ 25,00").first()).toBeVisible();
  await expect(page).toHaveURL(/\/accounts\/account-paid\?section=wallet$/);
});

test("live Console reads members, custom roles, backups and redacted activity", async ({
  page,
}) => {
  let invitationBody: unknown;
  let roleBody: unknown;
  let assignmentBody: unknown;
  let removedRoleBody: unknown;
  let removedMembershipBody: unknown;
  let backupBody: unknown;
  let deletionBody: unknown;
  await page.addInitScript(() => localStorage.setItem("gamewake_session", "signed-session"));
  await page.route("**/api/v1/me/accounts", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ accounts: [{ id: "account-live", name: "Grupo real", access: ownerAccess }] }),
    }),
  );
  await page.route("**/api/v1/accounts/account-live/worlds", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        worlds: [{ id: "world-live", name: "Mundo real", region: "sa-east-1", status: "sleeping" }],
      }),
    }),
  );
  await page.route("**/api/v1/accounts/account-live/wallet", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ wallet: { availableBalance: "18.50", statement: [] } }),
    }),
  );
  await page.route("**/api/v1/accounts/account-live/memberships", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        memberships: [
          { id: "member-owner", userId: "user-owner", roles: [{ id: "assignment-owner", role: "owner", kind: "predefined", worldId: null }] },
          { id: "member-friend", userId: "user-friend", roles: [{ id: "assignment-player", role: "player", kind: "predefined", worldId: null }] },
        ],
      }),
    }),
  );
  await page.route("**/api/v1/accounts/account-live/memberships/member-friend/roles", (route) => {
    assignmentBody = route.request().postDataJSON();
    return route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        membership: {
          id: "member-friend",
          userId: "user-friend",
          roles: [{ id: "assignment-custom", role: "role-saves", kind: "custom", worldId: null }],
        },
      }),
    });
  });
  await page.route("**/api/v1/accounts/account-live/memberships/member-friend/roles/assignment-custom", (route) => {
    removedRoleBody = route.request().postDataJSON();
    return route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ membership: { id: "member-friend", userId: "user-friend", roles: [{ id: "assignment-player", role: "player", kind: "predefined", worldId: null }] } }),
    });
  });
  await page.route("**/api/v1/accounts/account-live/memberships/member-friend", (route) => {
    removedMembershipBody = route.request().postDataJSON();
    return route.fulfill({ contentType: "application/json", body: JSON.stringify({ removed: true }) });
  });
  await page.route("**/api/v1/accounts/account-live/roles", (route) => {
    if (route.request().method() === "POST") {
      roleBody = route.request().postDataJSON();
      return route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({ role: { id: "role-operator", name: "Operador", permissions: ["world:view", "backup:create"] } }),
      });
    }
    return route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        predefinedRoles: ["owner", "manager", "player"],
        customRoles: [{ id: "role-saves", name: "Guardião dos saves", permissions: ["backup:create"] }],
        permissions: ["world:view", "backup:create", "backup:restore"],
      }),
    });
  });
  await page.route("**/api/v1/accounts/account-live/invitation-links", (route) => {
    invitationBody = route.request().postDataJSON();
    return route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify({ invitation: { id: "invitation-link" } }),
    });
  });
  await page.route("**/api/v1/accounts/account-live/worlds/world-live/backups", (route) => {
    if (route.request().method() === "POST") {
      backupBody = route.request().postDataJSON();
      return route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({ backup: { id: "backup-2", kind: "manual", sizeBytes: 1200, checksumVerified: true, createdAt: "2026-07-31T18:01:00+00:00" } }),
      });
    }
    return route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        backups: [{ id: "backup-1", kind: "manual", sizeBytes: 1200, checksumVerified: true, createdAt: "2026-07-31T18:00:00+00:00" }],
      }),
    });
  });
  await page.route("**/api/v1/accounts/account-live/worlds/world-live", (route) => {
    deletionBody = route.request().postDataJSON();
    return route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({ world: { id: "world-live", name: "Mundo real", region: "sa-east-1", status: "pending_deletion" } }),
    });
  });
  await page.route("**/api/v1/accounts/account-live/activity", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        events: [{ id: "event-1", action: "role_assignment.revoked", actorUserId: "user-owner", subjectId: "assignment-1", occurredAt: "2026-07-31T18:00:00+00:00" }],
      }),
    }),
  );
  await page.route("**/api/v1/accounts/account-live/worlds/world-live/operations", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        operations: [{ id: "operation-1", type: "sleep", status: "succeeded", phase: "complete", createdAt: "2026-07-31T17:00:00+00:00" }],
      }),
    }),
  );

  await page.goto("/accounts/account-live");
  await navigation(page, "members").click();
  await expect(page).toHaveURL(/\/accounts\/account-live\?section=members&world=world-live$/);
  await page.reload();
  await expect(page.getByTestId("members-panel")).toBeVisible();
  await expect(page.getByText("user-friend")).toBeVisible();
  await expect(page.locator(".advanced-roles strong", { hasText: "Guardião dos saves" })).toBeVisible();
  await page.getByTestId("create-invitation-link").click();
  await expect.poll(() => invitationBody).toEqual({ access: "play" });
  await expect(page.getByLabel("Link de convite criado")).toHaveValue(
    /\/convites\/account-live\/invitation-link$/,
  );
  await page.getByRole("button", { name: "Gerenciar Console" }).click();
  await page.getByLabel("Role do link de gerenciamento").selectOption("predefined:manager");
  await page.getByTestId("create-invitation-link").click();
  await expect.poll(() => invitationBody).toEqual({
    access: "console",
    predefinedRole: "manager",
  });
  await page.getByLabel("Nome da Role personalizada").fill("Operador");
  await page.getByLabel("Criar backups").check();
  await expectControlsSeparated(
    page.getByLabel("Nome da Role personalizada"),
    page.getByRole("group", { name: "Permissões da Role" }),
  );
  await page.getByLabel("Confirme Grupo real para criar Role").fill("Grupo real");
  await page.getByRole("button", { name: "Criar Role personalizada" }).click();
  await expect(page.locator(".advanced-roles strong", { hasText: "Operador" })).toBeVisible();
  expect(roleBody).toEqual({
    name: "Operador",
    permissions: ["world:view", "backup:create"],
    confirmedResourceName: "Grupo real",
  });
  await page.getByLabel("Nova Role para user-friend").selectOption("custom:role-saves");
  await page.locator(".member-row", { hasText: "user-friend" }).getByRole("button", { name: "Trocar" }).click();
  await expect(page.getByText("Confirmar nova Role")).toBeVisible();
  await page.locator(".role-confirmation-panel").getByRole("link", { name: "Renovar login Discord" }).evaluate((link) => {
    link.addEventListener("click", (event) => event.preventDefault(), { once: true });
    (link as HTMLAnchorElement).click();
  });
  expect(
    await page.evaluate(() => localStorage.getItem("gamewake:post-auth-return")),
  ).toBe("/accounts/account-live?section=members&world=world-live");
  await page.getByLabel("Confirme Grupo real para atribuir Role a user-friend").fill("Grupo real");
  await page.getByRole("button", { name: "Confirmar atribuição" }).click();
  await expect.poll(() => assignmentBody).toEqual({
    customRoleId: "role-saves",
    confirmedResourceName: "Grupo real",
  });
  await expect(page.getByText("Confirmar nova Role")).toHaveCount(0);
  await page.getByRole("button", { name: "Remover Role role-saves de user-friend" }).click();
  await expect(page.getByText("Remover Role de user-friend")).toBeVisible();
  await page.getByLabel("Confirme Grupo real para remover Role de user-friend").fill("Grupo real");
  await page.getByRole("button", { name: "Confirmar remoção da Role" }).click();
  await expect.poll(() => removedRoleBody).toEqual({ confirmedResourceName: "Grupo real" });
  await page.getByRole("button", { name: "Remover membro user-friend" }).click();
  await expect(page.getByText("Remover user-friend do grupo")).toBeVisible();
  await page.getByLabel("Confirme Grupo real para remover user-friend").fill("Grupo real");
  await page.getByRole("button", { name: "Confirmar remoção do jogador" }).click();
  await expect.poll(() => removedMembershipBody).toEqual({ confirmedResourceName: "Grupo real" });
  await expect(page.getByText("user-friend")).toHaveCount(0);
  await navigation(page, "backups").click();
  await expect(page.locator(".backup-row strong", { hasText: "Backup manual" })).toBeVisible();
  await page.getByRole("button", { name: "+ Backup manual" }).click();
  await expect(page.getByText("2 cópias protegidas")).toBeVisible();
  expect(backupBody).toMatchObject({ idempotencyKey: expect.any(String) });
  await page.getByText("Exclusão e portabilidade").click();
  await page.getByLabel("Confirme o nome do World").fill("Mundo real");
  await page.getByRole("button", { name: "Agendar exclusão" }).click();
  await expect(page.getByText(/Pending Deletion por sete dias/)).toBeVisible();
  expect(deletionBody).toMatchObject({
    confirmedResourceName: "Mundo real",
    idempotencyKey: expect.any(String),
  });
  await navigation(page, "activity").click();
  await expect(page.getByText("Role removida")).toBeVisible();
  await expect(page.getByText("Operação de sleep")).toBeVisible();
});
