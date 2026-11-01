import { expect, test } from "@playwright/test"
import { createUser } from "./utils/privateApi"
import { randomEmail, randomPassword } from "./utils/random"
import { logInUser } from "./utils/user"

test("Business settings no longer expose the shop name or VAT controls", async ({
  page,
}) => {
  await page.goto("/settings")
  await page.getByRole("tab", { name: "Business" }).click()
  await expect(page.getByLabel("Business name")).toHaveCount(0)
  await expect(page.getByLabel("Tax rate (%)")).toHaveCount(0)
  await expect(page.getByLabel("Timezone")).not.toHaveValue("")
  await expect(page.getByText("Preview:")).toContainText("₫")
})

test("Invalid timezone is rejected", async ({ page }) => {
  await page.goto("/settings")
  await page.getByRole("tab", { name: "Business" }).click()

  await page.getByLabel("Timezone").fill("Mars/Olympus")
  await page.getByRole("button", { name: "Save" }).click()

  await expect(
    page.getByText("Timezone must be a valid IANA timezone name"),
  ).toBeVisible()
})

test.describe("Non-owner", () => {
  test.use({ storageState: { cookies: [], origins: [] } })

  test("Cashier can read but not edit business settings", async ({ page }) => {
    const email = randomEmail()
    const password = randomPassword()
    await createUser({ email, password, role: "cashier" })
    await logInUser(page, email, password)

    await page.goto("/settings")
    await page.getByRole("tab", { name: "Business" }).click()

    await expect(page.getByLabel("Timezone")).toBeDisabled()
    await expect(page.getByLabel("Timezone")).not.toHaveValue("")
    await expect(
      page.getByText("Only the owner can change business settings."),
    ).toBeVisible()
    await expect(page.getByRole("button", { name: "Save" })).toHaveCount(0)
  })
})
