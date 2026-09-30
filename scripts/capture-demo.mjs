import { chromium } from "@playwright/test";
import { mkdir, copyFile } from "node:fs/promises";
await mkdir("docs/demo", { recursive: true });
const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1440, height: 1000 },
  recordVideo: { dir: "data/recording", size: { width: 1440, height: 1000 } },
});
const page = await context.newPage();
await page.goto(process.env.DEMO_URL || "http://127.0.0.1:5173");
await page.locator(".camera-clock").first().waitFor();
await page.waitForTimeout(2500);
await page.screenshot({ path: "docs/demo/dashboard.png", fullPage: true });
await page.screenshot({ path: "docs/demo/dashboard-slide.png" });
await page.getByTitle("Развернуть камеру").first().click();
await page.waitForTimeout(2200);
await page.keyboard.press("Escape");
await page.locator("nav").getByRole("button", { name: "Инциденты" }).click();
await page.waitForTimeout(1500);
await page.locator("tbody tr").first().click();
await page.waitForTimeout(1800);
await page.screenshot({ path: "docs/demo/incidents.png", fullPage: true });
await page.keyboard.press("Escape");
await page
  .locator("nav")
  .getByRole("button", { name: "Зоны безопасности" })
  .click();
await page.waitForTimeout(2000);
await page.screenshot({ path: "docs/demo/zones.png", fullPage: true });
await page
  .locator("nav")
  .getByRole("button", { name: "Аналитика", exact: true })
  .click();
await page.waitForTimeout(2000);
await page.screenshot({ path: "docs/demo/analytics.png", fullPage: true });
await page.locator("nav").getByRole("button", { name: "Тестовое видео", exact: true }).click();
await page.getByLabel("Видео с рабочими").evaluate(async (video) => {
  if (video.readyState < 2) await new Promise(resolve => video.addEventListener("loadeddata", resolve, {once:true}));
  await video.play();
});
await page.waitForTimeout(8000);
await page.getByLabel("Видео с рабочими").evaluate(video => video.pause());
await page.screenshot({ path: "docs/demo/workers-video.png", fullPage: true });
await page.locator(".sample-layout").screenshot({ path: "docs/demo/workers-video-slide.png" });
await page
  .locator("nav")
  .getByRole("button", { name: "Обзор", exact: true })
  .click();
await page.waitForTimeout(1800);
await context.close();
await copyFile(await page.video().path(), "docs/demo/hse-ai-video.webm");
await browser.close();
console.log("Demo saved: docs/demo/hse-ai-video.webm");
