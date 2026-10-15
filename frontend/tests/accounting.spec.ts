import { expect, type Page, test } from "@playwright/test"

import {
  AccountingService,
  InventoryService,
  PurchasingService,
} from "../src/client"
import { asSuperuser, uniqueSuffix } from "./utils/api"

test.use({ viewport: { width: 1280, height: 800 } })
test.setTimeout(120_000)

function parseMoney(text: string): number {
  const negative = text.includes("-") || text.includes("−")
  const digits = text.replace(/[^\d]/g, "")
  const value = Number(digits)
  return negative ? -value : value
}

async function labels(page: Page) {
  await page.goto("/expenses")
  const heading = page.getByRole("heading", { level: 1 })
  await expect(heading).toBeVisible()
  const title = await heading.innerText()
  return title === "Chi phí" ? vi : en
}

const en = {
  record: "Record expense",
  save: "Save",
  recorded: "Expense recorded",
  suppliers: "Suppliers",
  pay: "Pay supplier",
  paid: "Supplier payment recorded",
  cash: "Cash and bank",
  label: "Recorded",
  defaultPay: "Default for supplier payments",
}

const vi = {
  record: "Ghi chi phí",
  save: "Lưu",
  recorded: "Đã ghi chi phí",
  suppliers: "Nhà cung cấp",
  pay: "Trả nhà cung cấp",
  paid: "Đã ghi thanh toán",
  cash: "Tiền mặt và ngân hàng",
  label: "Đã ghi nhận",
  defaultPay: "Mặc định khi trả nhà cung cấp",
}

test("record an expense, pay a supplier in part, and see cash move", async ({
  page,
}) => {
  await asSuperuser()
  const suffix = uniqueSuffix()
  const categories = await InventoryService.readCategories()
  const item = await InventoryService.createItem({
    requestBody: {
      name: `Beans ${suffix}`,
      category_id: categories.data[0].id,
      item_type: "ingredient",
      base_unit: "g",
      purchase_unit: "g",
      conversion_factor: "1",
    },
  })
  const supplier = await PurchasingService.createSupplier({
    requestBody: { name: `Roaster ${suffix}` },
  })
  const today = new Date().toISOString().slice(0, 10)
  const receipt = await PurchasingService.createReceipt({
    requestBody: {
      supplier_id: supplier.id,
      receipt_date: today,
      lines: [
        {
          item_id: item.id,
          purchase_quantity: "1",
          purchase_unit_cost: "1000000",
        },
      ],
    },
  })
  await PurchasingService.postReceipt({
    receiptId: receipt.id,
    idempotencyKey: crypto.randomUUID(),
  })

  const before = await AccountingService.readAccounts()
  const drawer = before.data.find((account) => account.name === "Cash drawer")
  expect(drawer).toBeTruthy()
  const opening = Number(drawer!.balance)

  const copy = await labels(page)
  await page.getByRole("button", { name: copy.record }).click()
  await page.getByTestId("expense-category").click()
  await page.getByRole("option", { name: "Rent" }).click()
  await page.getByTestId("expense-amount").fill("150000")
  await page.getByTestId("expense-description").fill(`Rent ${suffix}`)
  await page.getByTestId("expense-account").click()
  await page.getByRole("option", { name: "Cash drawer" }).click()
  await page.getByTestId("save-expense").click()
  await expect(page.getByText(copy.recorded)).toBeVisible()

  await page.goto("/suppliers")
  await page
    .getByRole("textbox", {
      name:
        copy.suppliers === "Suppliers"
          ? "Search suppliers"
          : "Tìm nhà cung cấp",
    })
    .fill(supplier.name)
  await page.getByRole("button", { name: supplier.name, exact: true }).click()
  await expect(page.getByTestId("supplier-outstanding")).toContainText(
    "1.000.000",
  )
  await page.getByRole("button", { name: copy.pay }).click()
  await page.getByTestId("supplier-pay-amount").fill("400000")
  await page.getByTestId("supplier-pay-account").click()
  await page.getByRole("option", { name: "Cash drawer" }).click()
  await page.getByTestId("save-supplier-payment").click()
  await expect(page.getByText(copy.paid)).toBeVisible()
  await expect(page.getByTestId("supplier-outstanding")).toContainText(
    "600.000",
  )

  await page.goto("/cash")
  await expect(page.getByRole("heading", { name: copy.cash })).toBeVisible()
  const shown = await page.getByTestId("cash-account-cash").innerText()
  expect(parseMoney(shown) - opening).toBe(-550_000)
  await expect(page.getByTestId("cash-account-cash")).toContainText(copy.label)
  await expect(page.getByTestId("cash-account-bank")).toContainText(
    copy.defaultPay,
  )
})
