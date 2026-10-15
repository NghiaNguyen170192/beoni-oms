import { expect, type Page, test } from "@playwright/test"
import type { Role } from "../src/client"
import { createUser } from "./utils/privateApi"
import { randomEmail, randomPassword } from "./utils/random"
import { logInUser } from "./utils/user"

test.use({ storageState: { cookies: [], origins: [] } })

async function logInAs(page: Page, role: Role) {
  const email = randomEmail()
  const password = randomPassword()
  await createUser({ email, password, role })
  await logInUser(page, email, password)
}

for (const role of ["cashier", "inventory_staff"] as const) {
  test(`${role} sees only permitted navigation`, async ({ page }) => {
    await logInAs(page, role)

    const sidebar = page.locator("[data-sidebar='sidebar']")
    await expect(sidebar.getByRole("link", { name: "Dashboard" })).toBeVisible()
    await expect(sidebar.getByRole("link", { name: "Admin" })).toHaveCount(0)
    await expect(sidebar.getByRole("link", { name: "Audit Log" })).toHaveCount(
      0,
    )
  })

  test(`${role} is redirected away from admin pages`, async ({ page }) => {
    await logInAs(page, role)

    await page.goto("/admin")
    await expect(page).not.toHaveURL(/\/admin/)

    await page.goto("/admin/audit-log")
    await expect(page).not.toHaveURL(/\/admin/)
  })
}
