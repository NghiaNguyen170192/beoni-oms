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

const en = {
  search: "Search menu items",
  add: "Add",
  increase: "Increase",
  discount: "Order discount",
  value: "Value",
  apply: "Apply",
  takeaway: "Takeaway",
  complete: "Complete",
  print: "Print receipt",
  receipt: "Receipt",
  printButton: "Print",
  ownOrders: "Orders you created",
  number: "Number",
  filter: "Filter",
  empty: "No results found.",
  lineDiscount: "Discount",
  pay: "Pay and complete",
  record: "Record payment",
  refund: "Record refund",
  refundAmount: "Refund amount",
  reason: "Reason",
  recorded: "Refund recorded",
}

const vi = {
  search: "Tìm món",
  add: "Thêm",
  increase: "Tăng",
  discount: "Giảm giá đơn",
  value: "Giá trị",
  apply: "Áp dụng",
  takeaway: "Mang đi",
  complete: "Hoàn thành đơn",
  print: "In hóa đơn",
  receipt: "Hóa đơn",
  printButton: "In",
  ownOrders: "Đơn hàng bạn đã tạo",
  number: "Số đơn",
  filter: "Lọc",
  empty: "Không có kết quả.",
  lineDiscount: "Giảm giá",
  pay: "Thu và hoàn thành",
  record: "Ghi nhận thanh toán",
  refund: "Ghi nhận hoàn tiền",
  refundAmount: "Số tiền hoàn",
  reason: "Lý do",
  recorded: "Đã ghi nhận hoàn tiền",
}

async function labels(page: Page) {
  const settings = page.waitForResponse(
    (response) => response.url().includes("/api/v1/settings") && response.ok(),
  )
  await page.goto("/pos")
  await settings
  const heading = page.getByRole("heading", { name: /^(POS|Bán hàng)$/ })
  await expect(heading).toBeVisible()
  return (await heading.innerText()).trim() === "Bán hàng" ? vi : en
}

async function addToCart(
  page: Page,
  code: string,
  name: string,
  copy: typeof en,
) {
  await page.getByLabel(copy.search).fill(code)
  await page.getByRole("button", { name: `${copy.add} ${name}` }).click()
}

async function payCash(page: Page, copy: typeof en, tender?: string) {
  await page.getByRole("button", { name: "Cash" }).click()
  if (tender) {
    for (const digit of tender) {
      await page.getByRole("button", { name: digit, exact: true }).click()
    }
  } else {
    const total = (await page.getByTestId("order-total").innerText()).trim()
    await page.getByRole("button", { name: total, exact: true }).click()
  }
  await page.getByRole("button", { name: copy.pay }).click()
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
  const copy = await labels(page)
  await page.getByRole("radio", { name: copy.takeaway }).click()

  await addToCart(page, latte.code, latte.name, copy)
  await expect(page.getByTestId("cart-line")).toHaveCount(1)
  await page
    .getByRole("button", { name: `${copy.increase} ${latte.name}` })
    .click()
  await expect(page.getByTestId("cart-line-quantity").first()).toHaveText("2")
  await addToCart(page, croissant.code, croissant.name, copy)
  await expect(page.getByTestId("cart-line")).toHaveCount(2)
  await expect(page.getByTestId("order-total")).toContainText("85.000")

  await page.getByRole("button", { name: copy.discount }).click()
  await page.getByLabel(copy.value).fill("10")
  await page.getByRole("button", { name: copy.apply }).click()
  await expect(page.getByTestId("order-discount")).toContainText("8.500")
  await expect(page.getByTestId("order-total")).toContainText("76.500")

  await page.getByRole("button", { name: copy.complete }).click()
  await payCash(page, copy)
  const done = page.getByTestId("order-completed")
  await expect(done).toContainText("76.500")
  await expect(page.getByTestId("cart-line")).toHaveCount(0)

  const receiptPromise = context.waitForEvent("page")
  await done.getByRole("link", { name: copy.print }).click()
  const receipt = await receiptPromise
  await receipt.waitForLoadState()
  await expect(
    receipt.getByRole("article", { name: copy.receipt }),
  ).toContainText(latte.name)
  await expect(receipt.getByTestId("receipt-total")).toContainText("76.500")
  await expect(
    receipt.getByRole("button", { name: copy.printButton }),
  ).toBeVisible()
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
  const copy = await labels(page)
  await addToCart(page, tea.code, tea.name, copy)
  await expect(page.getByTestId("order-total")).toContainText("35.000")
  await expect(page.getByRole("button", { name: copy.discount })).toHaveCount(0)
  await expect(
    page.getByRole("button", { name: `${copy.lineDiscount} ${tea.name}` }),
  ).toHaveCount(0)
  await page.getByRole("button", { name: copy.complete }).click()
  await payCash(page, copy)
  const done = page.getByTestId("order-completed")
  await expect(done).toBeVisible()
  const ownNumber = (await done.textContent())?.match(/HD-\d{8}-\d{4}/)?.[0]
  expect(ownNumber).toBeTruthy()

  await page.goto("/orders")
  await expect(page.getByText(copy.ownOrders)).toBeVisible()
  const ownRow = page.getByRole("row").filter({ hasText: ownNumber! })
  await expect(ownRow).toContainText("Test User")

  await page.getByLabel(copy.number).fill(otherOrder.number)
  await page.getByRole("button", { name: copy.filter }).click()
  await expect(page.getByText(copy.empty)).toBeVisible()
})
