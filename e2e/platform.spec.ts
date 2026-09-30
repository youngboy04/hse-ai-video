import { test, expect } from "@playwright/test";

test("dashboard, live canvas, camera focus and mobile layout", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Центр безопасности" }),
  ).toBeVisible();
  // Allow cold local startup while waiting for actual camera data.
  await expect(page.locator(".camera-card")).toHaveCount(4, { timeout: 15000 });
  await expect(page.locator(".camera-clock").first()).not.toHaveText("—:—:—");
  await expect(page.locator(".error-banner")).toHaveCount(0);
  await page.screenshot({
    path: "test-results/dashboard-desktop.png",
    fullPage: true,
  });
  await page.getByTitle("Развернуть камеру").first().click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Разметка", exact: true }).click();
  await expect(page.getByRole("button", { name: "Разметка", exact: true })).toHaveAttribute(
    "aria-pressed",
    "false",
  );
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: "test-results/dashboard-mobile.png",
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  expect(errors).toEqual([]);
});

test("incident workflow, search, export and analytics", async ({ page }) => {
  await page.goto("/");
  await page.locator("nav").getByRole("button", { name: "Инциденты" }).click();
  await expect(page.locator("tbody tr").first()).toBeVisible();
  await page.locator("tbody tr").first().click();
  const dialog = page.getByRole("dialog");
  await dialog
    .getByPlaceholder("Результат проверки и принятые меры…")
    .fill("Проверено оператором E2E");
  if (await dialog.getByRole("button", { name: "Взять в работу" }).isVisible())
    await dialog.getByRole("button", { name: "Взять в работу" }).click();
  await dialog.getByRole("button", { name: "Закрыть инцидент" }).click();
  await expect(dialog.locator(".status-tag")).toHaveText("Закрыт");
  await page.keyboard.press("Escape");
  await page
    .getByPlaceholder("Камера, тип или ID трека")
    .fill("несуществующая камера");
  await expect(page.getByText("Событий не найдено")).toBeVisible();
  await page.getByRole("button", { name: "Очистить поиск" }).click();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Экспорт отчёта" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toContain(".csv");
  await page
    .locator("nav")
    .getByRole("button", { name: "Аналитика", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Типы нарушений" }),
  ).toBeVisible();
  await expect(page.locator('.recharts-bar-rectangle path').first()).toBeVisible();
  const barBox=await page.locator('.recharts-bar-rectangle path').first().boundingBox();
  expect(barBox?.width).toBeGreaterThan(5);
  await expect(page.locator('.recharts-area-curve')).toBeVisible();
});

test("polygon creation/deletion and settings", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(page.locator(".camera-card")).toHaveCount(4);
  await page
    .locator("nav")
    .getByRole("button", { name: "Зоны безопасности" })
    .click();
  const canvas = page.locator(".zone-editor canvas");
  const box = (await canvas.boundingBox())!;
  for (const [x, y] of [
    [0.2, 0.4],
    [0.4, 0.4],
    [0.4, 0.7],
    [0.2, 0.7],
  ])
    await canvas.click({ position: { x: box.width * x, y: box.height * y } });
  await page
    .getByPlaceholder("Название опасной зоны")
    .fill("E2E тестовая зона");
  await page.getByRole("button", { name: "Сохранить зону" }).click();
  const row = page
    .locator(".zone-list-item")
    .filter({ hasText: "E2E тестовая зона" });
  await expect(row).toBeVisible();
  await row.getByTitle("Удалить зону").click();
  await row
    .locator(".delete-confirm")
    .getByRole("button", { name: "Удалить зону", exact: true })
    .click();
  await expect(row).toHaveCount(0);
  await page
    .locator("nav")
    .getByRole("button", { name: "Настройки", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Состояние платформы" }),
  ).toBeVisible();
  await expect(page.getByText("SQLite", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Сохранить подключение" }).click();
  expect(errors).toEqual([]);
});

test("camera form validates and connects a demo source", async ({ page }) => {
  await page.goto("/");
  await page
    .getByRole("button", { name: "Добавить камеру", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await dialog
    .getByLabel("Название камеры", { exact: true })
    .fill("E2E камера");
  await dialog
    .getByLabel("Расположение", { exact: true })
    .fill("Корпус E2E · Тест");
  await dialog.getByLabel("Использовать демонстрационный источник").check();
  await dialog.getByRole("button", { name: "Добавить камеру" }).click();
  await expect(dialog).toHaveCount(0);
  await page
    .locator("nav")
    .getByRole("button", { name: "Камеры", exact: true })
    .click();
  const card = page
    .locator(".camera-card")
    .filter({ hasText: "E2E камера" })
    .last();
  await expect(card).toBeVisible();
  await card.getByRole("button", { name: "Остановить" }).click();
  await expect(card.getByRole("button", { name: "Включить" })).toBeVisible();
});
