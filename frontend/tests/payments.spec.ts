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

const en = {
  search: "Search menu items",
  add: "Add",
  complete: "Complete",
  pay: "Pay and complete",
  record: "Record payment",
  change: /Change preview/,
  view: "View",
  refund: "Record refund",
  amount: "Refund amount",
  reason: "Reason",
  recorded: "Refund recorded",
  number: "Number",
  filter: "Filter",
}

const vi = {
  search: "Tìm món",
  add: "Thêm",
  complete: "Hoàn thành đơn",
  pay: "Thu và hoàn thành",
  record: "Ghi nhận thanh toán",
  change: /Tiền thối tạm tính/,
  view: "Xem",
  refund: "Ghi nhận hoàn tiền",
  amount: "Số tiền hoàn",
  reason: "Lý do",
  recorded: "Đã ghi nhận hoàn tiền",
  number: "Số đơn",
  filter: "Lọc",
}

async function logInAs(page: Page, role: Role) {
  const email = randomEmail()
  const password = randomPassword()
  await createUser({ email, password, role })
  await logInUser(page, email, password)
}

async function copyFor(page: Page) {
  const settings = page.waitForResponse(
    (response) => response.url().includes("/api/v1/settings") && response.ok(),
  )
  await page.goto("/pos")
  await settings
  const heading = page.getByRole("heading", { name: /^(POS|Bán hàng)$/ })
  await expect(heading).toBeVisible()
  return (await heading.innerText()).trim() === "Bán hàng" ? vi : en
}

async function sell(page: Page, name: string, code: string, copy: typeof en) {
  await page.getByLabel(copy.search).fill(code)
  await page.getByRole("button", { name: `${copy.add} ${name}` }).click()
  await expect(page.getByTestId("cart-line")).toHaveCount(1)
  await page.getByRole("button", { name: copy.complete }).click()
  await page.getByRole("button", { name: "Cash" }).click()
}

test("cash tender shows change and completes the sale", async ({ page }) => {
  const suffix = uniqueSuffix()
  const item = await createMenuItem({ name: `Tea ${suffix}`, price: "35000" })
  await logInAs(page, "cashier")
  const copy = await copyFor(page)
  await sell(page, item.name, item.code, copy)
  for (const digit of "100000") {
    await page.getByRole("button", { name: digit, exact: true }).click()
  }
  await expect(page.getByText(copy.change)).toBeVisible()
  await page.getByRole("button", { name: copy.pay }).click()
  await expect(page.getByTestId("order-completed")).toContainText("35.000")
})

test("a sale can be split across two cash payments", async ({ page }) => {
  const suffix = uniqueSuffix()
  const item = await createMenuItem({ name: `Cake ${suffix}`, price: "50000" })
  await logInAs(page, "cashier")
  const copy = await copyFor(page)
  await sell(page, item.name, item.code, copy)
  for (const digit of "20000") {
    await page.getByRole("button", { name: digit, exact: true }).click()
  }
  await page.getByRole("button", { name: copy.record }).click()
  await expect(
    page.locator("span").filter({ hasText: "30.000" }),
  ).toBeVisible()
  for (const digit of "30000") {
    await page.getByRole("button", { name: digit, exact: true }).click()
  }
  await page.getByRole("button", { name: copy.pay }).click()
  await expect(page.getByTestId("order-completed")).toContainText("50.000")
})

test("manager records a partial refund and then the remainder", async ({
  page,
}) => {
  const suffix = uniqueSuffix()
  const item = await createMenuItem({ name: `Juice ${suffix}`, price: "40000" })
  const order = await createCompletedOrder(item.id)
  await logInAs(page, "manager")
  const copy = await copyFor(page)
  await page.goto("/orders")
  await page.getByLabel(copy.number).fill(order.number)
  await page.getByRole("button", { name: copy.filter }).click()
  await page
    .getByRole("button", { name: `${copy.view} ${order.number}` })
    .click()

  await page.getByRole("button", { name: copy.refund }).click()
  await page.getByLabel(copy.amount).fill("15000")
  await page.getByLabel(copy.reason).fill("spilled")
  await page.getByRole("button", { name: copy.refund }).click()
  await expect(page.getByText(copy.recorded)).toBeVisible()

  await page.getByRole("button", { name: copy.refund }).click()
  await page.getByLabel(copy.amount).fill("25000")
  await page.getByLabel(copy.reason).fill("rest")
  await page.getByRole("button", { name: copy.refund }).click()
  await expect(page.getByText(copy.recorded)).toBeVisible()
})
