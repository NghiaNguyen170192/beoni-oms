import { expect, test } from "@playwright/test"
import { SettingsService } from "../src/client"
import { asSuperuser } from "./utils/api"
import { createUser } from "./utils/privateApi"
import { randomEmail, randomPassword } from "./utils/random"

// The language is business-wide: run serially and always restore English.
test.describe.configure({ mode: "serial" })

test.afterAll(async () => {
  await asSuperuser()
  await SettingsService.updateLanguage({ requestBody: { language: "en" } })
})

test("Language page is under Admin and defaults to English", async ({
  page,
}) => {
  await page.goto("/")
  const sidebar = page.locator("[data-sidebar='sidebar']")
  await sidebar.getByRole("link", { name: "Language" }).click()

  await expect(page).toHaveURL(/\/admin\/language/)
  await expect(page.getByRole("heading", { name: "Language" })).toBeVisible()
  await expect(page.getByRole("radio", { name: "English" })).toHaveAttribute(
    "aria-checked",
    "true",
  )
})

test("Owner switches everyone to Vietnamese and back", async ({
  page,
  browser,
}) => {
  await page.goto("/admin/language")
  await page.getByRole("radio", { name: "Tiếng Việt" }).click()

  await expect(page.getByText("Đã cập nhật ngôn ngữ")).toBeVisible()
  await expect(page.getByRole("heading", { name: "Ngôn ngữ" })).toBeVisible()
  await expect(page.locator("html")).toHaveAttribute("lang", "vi")
  const sidebar = page.locator("[data-sidebar='sidebar']")
  await expect(sidebar.getByRole("link", { name: "Quản trị" })).toBeVisible()
  await expect(sidebar.getByRole("link", { name: "Kho hàng" })).toBeVisible()

  await page.reload()
  await expect(page.getByRole("heading", { name: "Ngôn ngữ" })).toBeVisible()

  // Another user sees the business language after signing in.
  const email = randomEmail()
  const password = randomPassword()
  await createUser({ email, password, role: "cashier" })
  const context = await browser.newContext({
    storageState: { cookies: [], origins: [] },
  })
  const cashierPage = await context.newPage()
  await cashierPage.goto("/login")
  await cashierPage.getByTestId("email-input").fill(email)
  await cashierPage.getByTestId("password-input").fill(password)
  await cashierPage.getByTestId("password-input").press("Enter")
  await cashierPage.waitForURL("/")
  const cashierSidebar = cashierPage.locator("[data-sidebar='sidebar']")
  await expect(
    cashierSidebar.getByRole("link", { name: "Bán hàng" }),
  ).toBeVisible()
  await context.close()

  await page.getByRole("radio", { name: "English" }).click()
  await expect(page.getByText("Language updated")).toBeVisible()
  await expect(page.getByRole("heading", { name: "Language" })).toBeVisible()
  await expect(sidebar.getByRole("link", { name: "Inventory" })).toBeVisible()
})

test("Non-owners cannot open the language page", async ({ browser }) => {
  const email = randomEmail()
  const password = randomPassword()
  await createUser({ email, password, role: "manager" })
  const context = await browser.newContext({
    storageState: { cookies: [], origins: [] },
  })
  const page = await context.newPage()
  await page.goto("/login")
  await page.getByTestId("email-input").fill(email)
  await page.getByTestId("password-input").fill(password)
  await page.getByTestId("password-input").press("Enter")
  await page.waitForURL("/")

  const sidebar = page.locator("[data-sidebar='sidebar']")
  await expect(sidebar.getByRole("link", { name: "Language" })).toHaveCount(0)
  await page.goto("/admin/language")
  await expect(page).not.toHaveURL(/\/admin\/language/)
  await context.close()
})
