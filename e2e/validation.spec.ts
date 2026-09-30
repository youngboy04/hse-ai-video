import { test, expect } from "@playwright/test";

test("image check overlays measured detections and clears stale results", async ({ page }) => {
  await page.route("**/api/validation/image", route => route.fulfill({ json: {
    scope: "person_detection", synthetic: false, width: 20, height: 20,
    latency_ms: 88.2, provider: "CPUExecutionProvider", image_sha256: "test-image",
    model: { file: "fixture.onnx", sha256: "test-model" },
    detections: [{ bbox: [.1,.1,.8,.9], confidence: .9 }], limitations: ["Тест интерфейса с фиксированным ответом"],
  } }));
  await page.goto("/");
  await page.locator("nav").getByRole("button", { name: "Проверка модели" }).click();
  await expect(page.getByRole("button", { name: "Проверить", exact: true })).toBeDisabled();
  const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=", "base64");
  await page.getByLabel("Изображение для проверки").setInputFiles({ name: "fixture.png", mimeType: "image/png", buffer: png });
  await page.getByRole("button", { name: "Проверить", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Обнаружено людей: 1" })).toBeVisible();
  await expect(page.locator(".validation-image svg rect")).toHaveCount(1);
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Результат JSON" }).click();
  expect((await download).suggestedFilename()).toBe("hse-image-result.json");
  await page.getByLabel("Порог уверенности").selectOption("0.5");
  await expect(page.locator(".validation-image svg")).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test("image check shows missing-model error without made-up results", async ({ page }) => {
  await page.route("**/api/validation/image", route => route.fulfill({ status: 503, json: { detail: "Модель не установлена" } }));
  await page.goto("/");
  await page.locator("nav").getByRole("button", { name: "Проверка модели" }).click();
  await page.getByLabel("Изображение для проверки").setInputFiles({ name: "bad.png", mimeType: "image/png", buffer: Buffer.from("not-image") });
  await page.getByRole("button", { name: "Проверить", exact: true }).click();
  await expect(page.getByRole("alert")).toHaveText("Модель не установлена");
  await expect(page.locator(".validation-image svg")).toHaveCount(0);
});
