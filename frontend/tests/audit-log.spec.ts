import { expect, test } from "@playwright/test"
import { createUser } from "./utils/privateApi"
import { randomEmail, randomPassword } from "./utils/random"

test("Owner sees navigation to admin and audit log", async ({ page }) => {
  await page.goto("/")

  const sidebar = page.locator("[data-sidebar='sidebar']")
  await expect(sidebar.getByRole("link", { name: "Admin" })).toBeVisible()
  await expect(sidebar.getByRole("link", { name: "Audit Log" })).toBeVisible()
})

test("Role change made in admin appears in the audit log", async ({ page }) => {
  const email = randomEmail()
  const user = await createUser({
    email,
    password: randomPassword(),
    role: "cashier",
  })

  await page.goto("/admin")
  const userRow = page.getByRole("row").filter({ hasText: email })
  await expect(userRow.getByText("Cashier")).toBeVisible()
  await userRow.getByRole("button").click()
  await page.getByRole("menuitem", { name: "Edit User" }).click()

  await page.getByLabel("Role").click()
  await page.getByRole("option", { name: "Manager" }).click()
  await page.getByRole("button", { name: "Save" }).click()

  await expect(page.getByText("User updated successfully")).toBeVisible()
  await expect(userRow.getByText("Manager")).toBeVisible()

  await page.goto("/admin/audit-log")
  await expect(page.getByRole("heading", { name: "Audit Log" })).toBeVisible()
  await page.getByLabel("Entity ID").fill(user.id)
  await page.getByRole("button", { name: "Filter" }).click()

  const entry = page.getByRole("row").filter({ hasText: "Role changed" })
  await expect(entry).toHaveCount(1)
  await expect(entry).toContainText(user.id)
  await expect(entry).toContainText("cashier")
  await expect(entry).toContainText("manager")
})
