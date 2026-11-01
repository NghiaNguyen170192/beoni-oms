import { expect, test } from "@playwright/test"
import { readBusinessTaxRate, updateBusinessTaxRate } from "./utils/api"
import { createUser } from "./utils/privateApi"
import { randomEmail, randomPassword } from "./utils/random"
import { logInUser } from "./utils/user"

let originalTaxRate = "0.00"

test.beforeEach(async () => {
  originalTaxRate = await readBusinessTaxRate()
})

test.afterEach(async () => {
  await updateBusinessTaxRate(originalTaxRate)
})

test("Owner configures the receipt shop name and POS fee types under Admin", async ({
  page,
}) => {
  await page.goto("/admin/fees")
  await expect(
    page.getByRole("heading", { name: "POS fees, tax, and shop name" }),
  ).toBeVisible()

  const shopName = page.getByLabel("Shop name printed on receipts")
  const originalName = await shopName.inputValue()
  const updatedName = `Beoni ${randomPassword().slice(0, 6)}`

  await shopName.fill(updatedName)
  await page
    .locator("form")
    .first()
    .getByRole("button", { name: "Save" })
    .click()
  await expect(page.getByText("Shop name updated")).toBeVisible()
  await page.reload()
  await expect(shopName).toHaveValue(updatedName)

  const taxRate = page.getByLabel("Tax rate (%)")
  const originalRate = await taxRate.inputValue()
  const updatedRate = originalRate === "8.00" ? "9" : "8"
  await taxRate.fill(updatedRate)
  await page
    .locator("form")
    .nth(1)
    .getByRole("button", { name: "Save" })
    .click()
  await expect(page.getByText("VAT rate updated")).toBeVisible()
  await page.reload()
  await expect(taxRate).toHaveValue(`${updatedRate}.00`)

  await taxRate.fill("100.01")
  await page
    .locator("form")
    .nth(1)
    .getByRole("button", { name: "Save" })
    .click()
  await expect(
    page.getByText("Tax rate must be between 0 and 100"),
  ).toBeVisible()

  const feeName = `Shipping ${randomPassword().slice(0, 6)}`
  await page.getByLabel("New fee name").fill(feeName)
  await page.getByRole("button", { name: "Add fee" }).click()

  const feeRow = page.locator("li").filter({
    has: page.getByLabel(`Fee name: ${feeName}`),
  })
  await expect(feeRow).toBeVisible()
  const feeNameInput = page.getByLabel(`Fee name: ${feeName}`)
  await feeNameInput.fill(`${feeName} updated`)
  await feeRow.getByRole("button", { name: "Save" }).click()

  const updatedFeeInput = page.getByLabel(`Fee name: ${feeName} updated`)
  await expect(updatedFeeInput).toBeVisible()
  const enabled = page.getByRole("checkbox", { name: "Enabled for POS" })
  await expect(enabled).toBeChecked()
  await enabled.click()
  await expect(enabled).not.toBeChecked()

  await shopName.fill(originalName)
  await page
    .locator("form")
    .first()
    .getByRole("button", { name: "Save" })
    .click()
  await expect(page.getByText("Shop name updated").last()).toBeVisible()
  expect(originalRate).toBe(originalTaxRate)
})

test.describe("Non-owner", () => {
  test.use({ storageState: { cookies: [], origins: [] } })

  test("Cashier cannot access POS fee settings", async ({ page }) => {
    const email = randomEmail()
    const password = randomPassword()
    await createUser({ email, password, role: "cashier" })
    await logInUser(page, email, password)

    await page.goto("/admin/fees")
    await expect(page).not.toHaveURL(/\/admin\/fees/)
  })
})
