import { readFileSync } from "node:fs"

import { expect, type Page, test } from "@playwright/test"

import {
  AccountingService,
  CatalogService,
  OrdersService,
  PaymentsService,
  ReportsService,
} from "../src/client"
import {
  asSuperuser,
  createCompletedOrder,
  createMenuItem,
  createOrderFeeType,
  uniqueSuffix,
} from "./utils/api"

function parseCsv(text: string): string[][] {
  const lines = text
    .replace(/^\uFEFF/, "")
    .trim()
    .split(/\r?\n/)
  return lines.map((line) => line.split(","))
}

function moneySum(rows: string[][], index: number): string {
  const cents = rows.reduce(
    (total, row) => total + Math.round(Number(row[index]) * 100),
    0,
  )
  return (cents / 100).toFixed(2)
}

async function csvOf(page: Page, testId: string): Promise<string[][]> {
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByTestId(testId).click(),
  ])
  const path = await download.path()
  if (!path) throw new Error(`No file for ${testId}`)
  const parsed = parseCsv(readFileSync(path, "utf8"))
  return parsed.slice(1)
}

test("dashboard shows today's metrics after a sale", async ({ page }) => {
  const item = await createMenuItem({
    name: `Report tea ${uniqueSuffix()}`,
    price: "25000",
    productType: "non_stock",
  })
  await createCompletedOrder(item.id)
  await asSuperuser()
  const dashboard = await ReportsService.readDashboard()
  await page.goto("/")
  await expect(page.getByTestId("dashboard-net-sales")).toHaveAttribute(
    "data-value",
    dashboard.net_sales,
  )
  await expect(page.getByTestId("dashboard-fees")).toHaveAttribute(
    "data-value",
    dashboard.fees,
  )
  await expect(page.getByTestId("dashboard-order-count")).toHaveAttribute(
    "data-value",
    String(dashboard.order_count),
  )
})

test("fee revenue is separate from product and category sales", async ({
  page,
}) => {
  const suffix = uniqueSuffix()
  await asSuperuser()
  const category = await CatalogService.createCategory({
    requestBody: { name: `Fee category ${suffix}` },
  })
  const item = await CatalogService.createItem({
    requestBody: {
      name: `Fee product ${suffix}`,
      price: "29000",
      category_id: category.id,
      product_type: "non_stock",
    },
  })
  const feeType = await createOrderFeeType(`Delivery ${suffix}`)
  const order = await OrdersService.createOrder({
    requestBody: {
      order_type: "takeaway",
      lines: [{ menu_item_id: item.id, quantity: "1" }],
    },
  })
  const orderWithFee = await OrdersService.replaceOrderFees({
    orderId: order.id,
    requestBody: {
      fees: [{ fee_type_id: feeType.id, amount: "5000" }],
    },
  })
  const methods = await PaymentsService.readPaymentMethods({ activeOnly: true })
  const cash = methods.data.find((method) => method.kind === "cash")
  if (!cash) throw new Error("Cash payment method is not seeded")
  await PaymentsService.createOrderPayment({
    orderId: order.id,
    idempotencyKey: crypto.randomUUID(),
    requestBody: { method_id: cash.id, amount: orderWithFee.total },
  })
  const completed = await OrdersService.completeOrder({
    orderId: order.id,
    idempotencyKey: crypto.randomUUID(),
  })

  const period = await ReportsService.readPreset({ preset: "today" })
  const dates = { dateFrom: period.date_from, dateTo: period.date_to }
  const [statement, income, products, categorySales] = await Promise.all([
    ReportsService.readStatement(dates),
    AccountingService.readIncome(dates),
    ReportsService.readProducts(dates),
    ReportsService.readSalesSummary({
      ...dates,
      groupBy: "day",
      categoryId: category.id,
    }),
  ])
  const incomeRow = income.data.find((row) => row.order_id === order.id)
  expect(incomeRow).toBeDefined()
  expect(incomeRow?.fees).toBe(completed.fee_total)
  expect(Number(incomeRow?.net_sales)).toBe(
    Number(completed.subtotal) +
      Number(completed.fee_total) -
      Number(completed.discount_total) -
      Number(completed.tax_total),
  )
  expect(Number(categorySales.net_sales)).toBe(Number(item.price))
  const product = products.data.find((row) => row.menu_item_id === item.id)
  expect(product).toBeDefined()
  expect(Number(product?.net_sales)).toBe(Number(item.price))
  expect(Number(statement.fees)).toBe(
    income.data.reduce((total, row) => total + Number(row.fees), 0),
  )

  await page.goto("/reports/profit")
  await expect(page.getByTestId("profit-fees")).toHaveAttribute(
    "data-value",
    statement.fees,
  )
  const incomeRowOnPage = page
    .getByTestId("income-row")
    .filter({ hasText: completed.number })
  await expect(incomeRowOnPage).toHaveAttribute("data-fee", completed.fee_total)
  await expect(incomeRowOnPage.getByRole("cell").nth(1)).toContainText("5.000")
})

test("exported reports match the on-screen rows and totals", async ({
  page,
}) => {
  await asSuperuser()
  const period = await ReportsService.readPreset({ preset: "today" })

  await page.goto("/reports/sales")
  const salesNet = page.getByTestId("sales-net")
  await expect(salesNet).toBeVisible()
  const salesRows = await csvOf(page, "export-sales-summary")
  await expect(salesNet).toHaveAttribute("data-count", String(salesRows.length))
  const salesTotal = await salesNet.getAttribute("data-value")
  expect(moneySum(salesRows, 4)).toBe(Number(salesTotal).toFixed(2))

  const productNet = page.getByTestId("product-net")
  const productRows = await csvOf(page, "export-products")
  await expect(productNet).toHaveAttribute(
    "data-count",
    String(productRows.length),
  )
  const productTotal = await productNet.getAttribute("data-value")
  expect(moneySum(productRows, 4)).toBe(Number(productTotal).toFixed(2))

  await page.goto("/reports/inventory")
  const movementCount = page.getByTestId("movement-count")
  await expect(movementCount).toBeAttached()
  const movementRows = await csvOf(page, "export-movements")
  await expect(movementCount).toHaveAttribute(
    "data-count",
    String(movementRows.length),
  )
  const closings = await page
    .getByTestId("movement-row")
    .evaluateAll((rows) =>
      rows.map((row) => row.getAttribute("data-closing") ?? "").sort(),
    )
  const csvClosings = movementRows.map((row) => row[9]).sort()
  expect(csvClosings).toEqual(closings)

  await page.goto("/reports/profit")
  const profitNet = page.getByTestId("profit-net")
  await expect(profitNet).toBeVisible()
  const statementRows = await csvOf(page, "export-statement")
  expect(statementRows).toHaveLength(1)
  const profitValue = await profitNet.getAttribute("data-value")
  const profitFees = await page
    .getByTestId("profit-fees")
    .getAttribute("data-value")
  expect(Number(statementRows[0][0]).toFixed(2)).toBe(
    Number(profitFees).toFixed(2),
  )
  expect(Number(statementRows[0][1]).toFixed(2)).toBe(
    Number(profitValue).toFixed(2),
  )
  const operating = page.getByTestId("profit-operating")
  const operatingValue = await operating.getAttribute("data-value")
  expect(Number(statementRows[0][6]).toFixed(2)).toBe(
    Number(operatingValue).toFixed(2),
  )

  const expenseTotal = page.getByTestId("expense-total")
  const expenseRows = await csvOf(page, "export-expenses")
  await expect(expenseTotal).toHaveAttribute(
    "data-count",
    String(expenseRows.length),
  )
  const expenseValue = await expenseTotal.getAttribute("data-value")
  expect(moneySum(expenseRows, 1)).toBe(Number(expenseValue).toFixed(2))

  const incomeCount = page.getByTestId("income-count")
  const incomeRows = await csvOf(page, "export-income")
  await expect(incomeCount).toHaveAttribute(
    "data-count",
    String(incomeRows.length),
  )
  const incomeNets = await page
    .getByTestId("income-row")
    .evaluateAll((rows) =>
      rows.map((row) => Number(row.getAttribute("data-net")).toFixed(2)).sort(),
    )
  const incomeFees = await page
    .getByTestId("income-row")
    .evaluateAll((rows) =>
      rows.map((row) => Number(row.getAttribute("data-fee")).toFixed(2)).sort(),
    )
  expect(incomeRows.map((row) => Number(row[4]).toFixed(2)).sort()).toEqual(
    incomeFees,
  )
  expect(incomeRows.map((row) => Number(row[7]).toFixed(2)).sort()).toEqual(
    incomeNets,
  )

  await page.goto("/payments")
  await page.locator("#pay-from").fill(period.date_from)
  await page.locator("#pay-to").fill(period.date_to)
  const paymentsCount = page.getByTestId("payments-count")
  await Promise.all([
    page.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/payments?") && response.ok(),
    ),
    page.getByTestId("payments-filter").click(),
  ])
  const paymentRows = await csvOf(page, "export-payments")
  await expect(paymentsCount).toHaveAttribute(
    "data-count",
    String(paymentRows.length),
  )
  const shown = await page
    .locator("[data-amount]")
    .evaluateAll((rows) =>
      rows
        .map((row) => Number(row.getAttribute("data-amount")).toFixed(2))
        .sort(),
    )
  if (shown.length === paymentRows.length) {
    expect(paymentRows.map((row) => Number(row[3]).toFixed(2)).sort()).toEqual(
      shown,
    )
  }
})
