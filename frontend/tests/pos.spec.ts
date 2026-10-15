import { expect, type Page, test } from "@playwright/test"
import type { Role } from "../src/client"
import { createCompletedOrder, createMenuItem, uniqueSuffix } from "./utils/api"
import { createUser } from "./utils/privateApi"
import { randomEmail, randomPassword } from "./utils/random"
import { logInUser } from "./utils/user"

test.use({
  storageState: { cookies: [], origins: [] },
  viewport: { width: 1024, height: 768 },
  hasTouch: true,
})

async function logInAs(page: Page, role: Role) {
  const email = randomEmail()
  const password = randomPassword()
  await createUser({ email, password, role })
  await logInUser(page, email, password)
  return email
}

async function addToCart(page: Page, code: string, name: string) {
  await page.getByLabel("Search menu items").fill(code)
  await page.getByRole("button", { name: `Add ${name}` }).click()
}

test("Manager rings up a discounted takeaway order and prints the receipt", async ({
  page,
  context,
}) => {
  const suffix = uniqueSuffix()
  const latte = await createMenuItem({
    name: `Latte ${suffix}`,
    price: "30000",
  })
  const croissant = await createMenuItem({
    name: `Croissant ${suffix}`,
    price: "25000",
  })

  await logInAs(page, "manager")
  await page.goto("/pos")
  await page.getByRole("radio", { name: "Takeaway" }).click()

  await addToCart(page, latte.code, latte.name)
  await expect(page.getByTestId("cart-line")).toHaveCount(1)
  await page.getByRole("button", { name: `Increase ${latte.name}` }).click()
  await expect(page.getByTestId("cart-line-quantity").first()).toHaveText("2")
  await addToCart(page, croissant.code, croissant.name)
  await expect(page.getByTestId("cart-line")).toHaveCount(2)
  await expect(page.getByTestId("order-total")).toContainText("85.000")

  await page.getByRole("button", { name: "Order discount" }).click()
  await page.getByLabel("Value").fill("10")
  await page.getByRole("button", { name: "Apply" }).click()
  await expect(page.getByTestId("order-discount")).toContainText("8.500")
  await expect(page.getByTestId("order-total")).toContainText("76.500")

  await page.getByRole("button", { name: "Complete" }).click()
  await expect(page.getByText(/Order HD-\d{8}-\d{4} completed/)).toBeVisible()
  const done = page.getByTestId("order-completed")
  await expect(done).toContainText("76.500")
  await expect(page.getByTestId("cart-line")).toHaveCount(0)

  const receiptPromise = context.waitForEvent("page")
  await done.getByRole("link", { name: "Print receipt" }).click()
  const receipt = await receiptPromise
  await receipt.waitForLoadState()
  await expect(receipt.getByRole("article", { name: "Receipt" })).toContainText(
    latte.name,
  )
  await expect(receipt.getByTestId("receipt-total")).toContainText("76.500")
  await expect(receipt.getByRole("button", { name: "Print" })).toBeVisible()
})

test("Cashier sees only their own orders and cannot discount", async ({
  page,
}) => {
  const suffix = uniqueSuffix()
  const tea = await createMenuItem({
    name: `Trà đào ${suffix}`,
    price: "35000",
  })
  const otherOrder = await createCompletedOrder(tea.id)

  await logInAs(page, "cashier")
  await page.goto("/pos")
  await addToCart(page, tea.code, tea.name)
  await expect(page.getByTestId("order-total")).toContainText("35.000")
  await expect(
    page.getByRole("button", { name: "Order discount" }),
  ).toHaveCount(0)
  await expect(
    page.getByRole("button", { name: `Discount ${tea.name}` }),
  ).toHaveCount(0)
  await page.getByRole("button", { name: "Complete" }).click()
  const done = page.getByTestId("order-completed")
  await expect(done).toBeVisible()
  const ownNumber = (await done.textContent())?.match(/HD-\d{8}-\d{4}/)?.[0]
  expect(ownNumber).toBeTruthy()

  await page.goto("/orders")
  await expect(page.getByText("Orders you created")).toBeVisible()
  const ownRow = page.getByRole("row").filter({ hasText: ownNumber! })
  await expect(ownRow).toContainText("Test User")

  await page.getByLabel("Number").fill(otherOrder.number)
  await page.getByRole("button", { name: "Filter" }).click()
  await expect(page.getByText("No results found.")).toBeVisible()
})
