import { expect, test } from "@playwright/test";

function navigation(page: import("@playwright/test").Page, section: string) {
  return page.locator(`[data-testid="nav-${section}"]:visible`);
}

test("landing communicates the product and starts Discord onboarding", async ({
  page,
}) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: /Seu mundo fica/ })).toBeVisible();
  const signIn = page.getByRole("link", { name: "Entrar com Discord" }).first();
  await expect(signIn).toHaveAttribute(
    "href",
    "/auth/discord/start",
  );
  await expect(page.getByText("Pague pelo tempo de jogo")).toBeVisible();
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

  await navigation(page, "members").click();
  await page.getByTestId("invite-friends").click();
  await expect(page.getByText("Caio")).toBeVisible();

  await navigation(page, "worlds").click();
  await page.getByTestId("wake-world").click();
  await expect(page.getByRole("status")).toContainText("Restaurando World");
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

test("OAuth callback stores the short-lived session and routes an existing member", async ({
  page,
}) => {
  await page.route("**/api/v1/me/accounts", async (route) => {
    expect(route.request().headers().authorization).toBe("Bearer signed-session");
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        accounts: [{ id: "account-live", name: "Grupo real", discordGuildId: null }],
      }),
    });
  });

  await page.goto("/auth/callback#session=signed-session");

  await expect(page).toHaveURL(/\/accounts\/account-live$/);
  expect(await page.evaluate(() => sessionStorage.getItem("gamewake_session"))).toBe(
    "signed-session",
  );
});

test("authenticated onboarding creates a real account and Palworld through the API", async ({
  page,
}) => {
  let accountBody: unknown;
  let worldBody: unknown;
  await page.addInitScript(() => sessionStorage.setItem("gamewake_session", "signed-session"));
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
  expect(accountBody).toEqual({ name: "Grupo novo" });
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
  await page.addInitScript(() => sessionStorage.setItem("gamewake_session", "signed-session"));
  await page.route("**/api/v1/me/accounts", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        accounts: [{ id: "account-live", name: "Grupo real", discordGuildId: null }],
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
      body: JSON.stringify({ operation: { id: "operation-live", status: "pending" } }),
    });
  });

  await page.goto("/accounts/account-live");
  await expect(page.getByText("Mundo real")).toBeVisible();
  await expect(page.getByText("R$ 18,50").first()).toBeVisible();
  await page.getByTestId("wake-world").click();

  expect(wakeBody).toMatchObject({ idempotencyKey: expect.any(String) });
  await expect(page.getByRole("status")).toContainText("Restaurando World");
});
