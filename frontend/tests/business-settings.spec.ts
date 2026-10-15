import { expect, test } from "@playwright/test"
import { createUser } from "./utils/privateApi"
import { randomEmail, randomPassword } from "./utils/random"
import { logInUser } from "./utils/user"

test("Owner updates business settings", async ({ page }) => {
  await page.goto("/settings")
  await page.getByRole("tab", { name: "Business" }).click()

  const name = page.getByLabel("Business name")
  await expect(name).toBeEnabled()
  const originalName = await name.inputValue()
  const updatedName = `Beoni ${randomPassword().slice(0, 6)}`

  await name.fill(updatedName)
  await page.getByRole("button", { name: "Save" }).click()
  await expect(page.getByText("Business settings updated")).toBeVisible()

  await page.reload()
  await page.getByRole("tab", { name: "Business" }).click()
  await expect(page.getByLabel("Business name")).toHaveValue(updatedName)
  await expect(page.getByText("Preview:")).toContainText("₫")

  await page.getByLabel("Business name").fill(originalName)
  await page.getByRole("button", { name: "Save" }).click()
  await expect(page.getByText("Business settings updated").last()).toBeVisible()
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
