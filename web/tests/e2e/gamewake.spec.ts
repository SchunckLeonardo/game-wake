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

test("live Console reads members, custom roles, backups and redacted activity", async ({
  page,
}) => {
  let invitationBody: unknown;
  let roleBody: unknown;
  let assignmentBody: unknown;
  let backupBody: unknown;
  await page.addInitScript(() => sessionStorage.setItem("gamewake_session", "signed-session"));
  await page.route("**/api/v1/me/accounts", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ accounts: [{ id: "account-live", name: "Grupo real" }] }),
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
          { id: "member-owner", userId: "user-owner", roles: [{ role: "owner", kind: "predefined", worldId: null }] },
          { id: "member-friend", userId: "user-friend", roles: [{ role: "player", kind: "predefined", worldId: null }] },
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
          roles: [
            { role: "player", kind: "predefined", worldId: null },
            { role: "role-saves", kind: "custom", worldId: null },
          ],
        },
      }),
    });
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
  await page.route("**/api/v1/accounts/account-live/invitations", (route) => {
    invitationBody = route.request().postDataJSON();
    return route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify({ invitations: [] }),
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
  await page.route("**/api/v1/accounts/account-live/activity", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        events: [{ id: "event-1", action: "role_assignment.revoked", actorUserId: "user-owner", subjectId: "assignment-1", occurredAt: "2026-07-31T18:00:00+00:00" }],
      }),
    }),
  );

  await page.goto("/accounts/account-live");
  await navigation(page, "members").click();
  await expect(page.getByText("user-friend")).toBeVisible();
  await expect(page.locator(".advanced-roles strong", { hasText: "Guardião dos saves" })).toBeVisible();
  await page.getByLabel("IDs dos amigos").fill("user-a, user-b");
  await page.getByTestId("invite-friends").click();
  expect(invitationBody).toEqual({ invitedUserIds: ["user-a", "user-b"] });
  await page.getByLabel("Nome da Role personalizada").fill("Operador");
  await page.getByLabel("Criar backups").check();
  await page.getByLabel("Confirme o nome da conta").fill("Grupo real");
  await page.getByRole("button", { name: "Criar Role personalizada" }).click();
  await expect(page.locator(".advanced-roles strong", { hasText: "Operador" })).toBeVisible();
  expect(roleBody).toEqual({
    name: "Operador",
    permissions: ["world:view", "backup:create"],
    confirmedResourceName: "Grupo real",
  });
  await page.getByLabel("Nova Role para user-friend").selectOption("custom:role-saves");
  await page.getByLabel("Confirme o nome da conta").fill("Grupo real");
  await page.locator(".member-row", { hasText: "user-friend" }).getByRole("button", { name: "Atribuir" }).click();
  expect(assignmentBody).toEqual({
    customRoleId: "role-saves",
    confirmedResourceName: "Grupo real",
  });
  await navigation(page, "backups").click();
  await expect(page.locator(".backup-row strong", { hasText: "Backup manual" })).toBeVisible();
  await page.getByRole("button", { name: "+ Backup manual" }).click();
  await expect(page.getByText("2 cópias protegidas")).toBeVisible();
  expect(backupBody).toMatchObject({ idempotencyKey: expect.any(String) });
  await navigation(page, "activity").click();
  await expect(page.getByText("Role removida")).toBeVisible();
});
