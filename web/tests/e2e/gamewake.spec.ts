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
  await page.getByLabel("Limite mensal do World").fill("100");
  await page.getByRole("button", { name: "Salvar orçamento" }).click();
  await expect(page.getByRole("button", { name: "Orçamento salvo ✓" })).toBeVisible();

  await navigation(page, "members").click();
  await page.getByTestId("invite-friends").click();
  await expect(page.getByText("Caio")).toBeVisible();

  await navigation(page, "worlds").click();
  await page.getByTestId("wake-world").click();
  await expect(page.getByRole("dialog", { name: "Confirmar despertar de Palpagos" })).toContainText("R$ 5,50/h");
  await page.getByRole("button", { name: "Confirmar e acordar" }).click();
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

test("OAuth callback stores the short-lived session and selected Discord server", async ({
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

  await page.goto(
    "/auth/callback#session=signed-session&discordGuildId=123456789012345678",
  );

  await expect(page).toHaveURL(/\/accounts\/account-live$/);
  expect(await page.evaluate(() => sessionStorage.getItem("gamewake_session"))).toBe(
    "signed-session",
  );
  expect(
    await page.evaluate(() => sessionStorage.getItem("gamewake_discord_guild_id")),
  ).toBe("123456789012345678");
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
    body: JSON.stringify({ accounts: [{ id: "account-live" }] }),
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
    sessionStorage.setItem("gamewake_session", "signed-session");
    sessionStorage.setItem("gamewake_discord_guild_id", "123456789012345678");
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
    await page.evaluate(() => sessionStorage.getItem("gamewake_discord_guild_id")),
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
      body: JSON.stringify({ estimate: { currency: "BRL", hourlyRate: "5.50", minimumReservation: "2.30", reservedMinutes: 25 } }),
    });
  });

  await page.goto("/accounts/account-live");
  await expect(page.getByText("Mundo real")).toBeVisible();
  await expect(page.getByText("R$ 18,50").first()).toBeVisible();
  await page.getByTestId("wake-world").click();
  await expect(page.getByRole("dialog", { name: "Confirmar despertar de Mundo real" })).toContainText("R$ 5,50/h");
  await page.getByRole("button", { name: "Confirmar e acordar" }).click();

  expect(wakeBody).toMatchObject({ idempotencyKey: expect.any(String) });
  await expect(page.getByRole("status")).toContainText("Restaurando World");
});

test("live Console switches Worlds and persists Auto Sleep and World Budget", async ({ page }) => {
  let settingsBody: unknown;
  let budgetBody: unknown;
  await page.addInitScript(() => sessionStorage.setItem("gamewake_session", "signed-session"));
  await page.route("**/api/v1/me/accounts", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ accounts: [{ id: "account-live", name: "Grupo real" }] }),
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

test("Discord-bootstrapped account creates its first World from the Console", async ({
  page,
}) => {
  let createdWorldBody: unknown;
  await page.addInitScript(() => sessionStorage.setItem("gamewake_session", "signed-session"));
  await page.route("**/api/v1/me/accounts", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ accounts: [{ id: "account-empty", name: "Grupo do Discord" }] }),
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
  await page.getByRole("button", { name: "+ Novo World" }).click();
  await page.getByLabel("Nome do novo World").fill("Primeiro World");
  await page.getByRole("button", { name: "Criar World" }).click();

  await expect(page.getByRole("heading", { name: "Primeiro World" })).toBeVisible();
  expect(createdWorldBody).toMatchObject({
    name: "Primeiro World",
    gameTemplateId: "palworld:1",
    region: "sa-east-1",
    runtimeProfileId: "palworld-small",
  });
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
          roles: [
            { id: "assignment-player", role: "player", kind: "predefined", worldId: null },
            { id: "assignment-custom", role: "role-saves", kind: "custom", worldId: null },
          ],
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
  await page.getByRole("button", { name: "Remover Role role-saves de user-friend" }).click();
  await expect.poll(() => removedRoleBody).toEqual({ confirmedResourceName: "Grupo real" });
  await page.getByRole("button", { name: "Remover membro user-friend" }).click();
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
