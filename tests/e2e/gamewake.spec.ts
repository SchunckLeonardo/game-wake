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
    "/auth/discord/start?return_to=%2Fconsole",
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
