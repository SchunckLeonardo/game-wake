import { chromium } from "../../web/node_modules/playwright/index.mjs";

const browser = await chromium.launch({ headless: true });
const surfaces = [
  ["landing", "/"],
  ["console", "/console"],
  ["onboarding", "/onboarding"],
  ["auth-callback", "/auth/callback"],
  ["activity", "/activity"],
];

for (const viewport of [
  { name: "desktop", width: 1440, height: 1000, isMobile: false },
  { name: "mobile", width: 390, height: 844, isMobile: true },
]) {
  const context = await browser.newContext({
    deviceScaleFactor: 1,
    isMobile: viewport.isMobile,
    locale: "pt-BR",
    viewport: { width: viewport.width, height: viewport.height },
  });

  for (const [name, pathname] of surfaces) {
    const page = await context.newPage();
    await page.goto(`http://localhost:3000${pathname}`, { waitUntil: "networkidle" });
    await page.screenshot({
      fullPage: true,
      path: new URL(`./${name}-${viewport.name}.png`, import.meta.url).pathname,
    });
    await page.close();
  }

  await context.close();
}

await browser.close();
