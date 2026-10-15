import { expect, type Page, test } from "@playwright/test"
import type { Role } from "../src/client"
import { firstSuperuser, firstSuperuserPassword } from "./config"
import { createMenuItem, findMenuItem, uniqueSuffix } from "./utils/api"
import { createUser } from "./utils/privateApi"
import { randomEmail, randomPassword } from "./utils/random"
import { logInUser, logOutUser } from "./utils/user"

test.use({ storageState: { cookies: [], origins: [] } })

async function logInAs(page: Page, role: Role) {
  const email = randomEmail()
  const password = randomPassword()
  await createUser({ email, password, role })
  await logInUser(page, email, password)
}

test("Manager creates a category and item, changes the price, and marks it unavailable", async ({
  page,
}) => {
  const suffix = uniqueSuffix()
  const categoryName = `Sinh tố ${suffix}`
  const itemName = `Sinh tố bơ ${suffix}`

  await logInAs(page, "manager")
  await page.goto("/menu")
  await expect(page.getByRole("heading", { name: "Menu" })).toBeVisible()

  await page.getByRole("button", { name: "Categories" }).click()
  await page.getByLabel("New category name").fill(categoryName)
  await page.getByRole("button", { name: "Add", exact: true }).click()
  await expect(page.getByText("Category created")).toBeVisible()
  await expect(page.getByLabel(`Category name ${categoryName}`)).toBeVisible()
  await page.keyboard.press("Escape")

  await page.getByRole("button", { name: "Add Item" }).click()
  await page.getByLabel("Price").fill("29000")
  await page.getByLabel("Name").fill(itemName)
  await page.getByLabel("Category").click()
  await page.getByRole("option", { name: categoryName }).click()
  await page.getByRole("button", { name: "Save" }).click()
  await expect(page.getByText("Menu item created")).toBeVisible()

  await page.getByRole("tab", { name: categoryName }).click()
  const row = page.getByRole("row").filter({ hasText: itemName })
  await expect(row).toContainText(/MENU-\d{5}/)
  await expect(row).toContainText("29.000")

  await row.getByRole("button", { name: `Edit ${itemName}` }).click()
  await page.getByLabel("Price").fill("35000")
  await page.getByRole("button", { name: "Save" }).click()
  await expect(page.getByText("Menu item updated")).toBeVisible()
  await expect(row).toContainText("35.000")

  const available = row.getByRole("checkbox", {
    name: `Available ${itemName}`,
  })
  await expect(available).toBeChecked()
  await available.click()
  await expect(available).not.toBeChecked()

  // The price change is visible in the audit log for the owner.
  const item = await findMenuItem(itemName)
  expect(item.code).toMatch(/^MENU-\d{5}$/)
  await expect(row).toContainText(item.code)
  await logOutUser(page)
  await logInUser(page, firstSuperuser, firstSuperuserPassword)
  await page.goto("/admin/audit-log")
  await page.getByLabel("Entity type").fill("menu_item")
  await page.getByLabel("Entity ID").fill(item.id)
  await page.getByRole("button", { name: "Filter" }).click()
  const entry = page
    .getByRole("row")
    .filter({ hasText: "29000" })
    .filter({ hasText: "35000" })
  await expect(entry).toHaveCount(1)
})

test("Cashier sees a read-only menu", async ({ page }) => {
  const itemName = `Bạc xỉu ${uniqueSuffix()}`
  const item = await createMenuItem({ name: itemName, price: "32000" })

  await logInAs(page, "cashier")
  await page.goto("/menu")
  await expect(page.getByRole("heading", { name: "Menu" })).toBeVisible()
  await expect(page.getByText("Current menu and prices")).toBeVisible()

  await page.getByLabel("Search menu").fill(item.code)
  const row = page.getByRole("row").filter({ hasText: item.code })
  await expect(row).toContainText(itemName)
  await expect(row).toContainText("32.000")

  await expect(page.getByRole("button", { name: "Add Item" })).toHaveCount(0)
  await expect(page.getByRole("button", { name: "Categories" })).toHaveCount(0)
  await expect(row.getByRole("button")).toHaveCount(0)
  await expect(row.getByRole("checkbox")).toHaveCount(0)
})
