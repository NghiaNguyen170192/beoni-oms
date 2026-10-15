import { expect, type Page, test } from "@playwright/test"

import {
  type InventoryItemPublic,
  InventoryService,
  PurchasingService,
} from "../src/client"
import { asSuperuser, createMenuItem, uniqueSuffix } from "./utils/api"

test.use({ viewport: { width: 1280, height: 800 } })

async function stockItem(options: {
  name: string
  itemType: "ingredient" | "merchandise"
  unit: "g" | "ml" | "piece"
  quantity: string
  unitCost: string
}): Promise<InventoryItemPublic> {
  await asSuperuser()
  const categories = await InventoryService.readCategories()
  const item = await InventoryService.createItem({
    requestBody: {
      name: options.name,
      category_id: categories.data[0].id,
      item_type: options.itemType,
      base_unit: options.unit,
      purchase_unit: options.unit,
      conversion_factor: "1",
    },
  })
  const supplier = await PurchasingService.createSupplier({
    requestBody: { name: `Supplier ${options.name}` },
  })
  const receipt = await PurchasingService.createReceipt({
    requestBody: {
      supplier_id: supplier.id,
      receipt_date: new Date().toISOString().slice(0, 10),
      lines: [
        {
          item_id: item.id,
          purchase_quantity: options.quantity,
          purchase_unit_cost: options.unitCost,
        },
      ],
    },
  })
  await PurchasingService.postReceipt({
    receiptId: receipt.id,
    idempotencyKey: crypto.randomUUID(),
  })
  return item
}

async function saveRecipe(
  page: Page,
  menuCode: string,
  menuName: string,
  ingredientName: string,
  quantity: string,
) {
  await page.goto("/recipes")
  await page.getByTestId("recipes-search").fill(menuCode)
  await page.getByRole("button", { name: menuName, exact: true }).click()
  await page.getByRole("button", { name: /New version|Phiên bản mới/ }).click()
  await page.getByLabel(/Effective from|Hiệu lực từ/).fill("2020-01-01T08:00")
  await page.getByTestId("recipe-line-search").fill(ingredientName)
  await page.getByRole("button", { name: ingredientName }).click()
  await page.getByLabel(/Quantity|Số lượng/).fill(quantity)
  await page.getByTestId("save-recipe").click()
  await expect(page.getByText("v1")).toBeVisible()
}

test("a recipe deducts stock, a shortage is shown, and a bottle can be returned", async ({
  page,
}) => {
  test.setTimeout(120_000)
  const suffix = uniqueSuffix()
  const beans = await stockItem({
    name: `Beans ${suffix}`,
    itemType: "ingredient",
    unit: "g",
    quantity: "1000",
    unitCost: "400",
  })
  const milk = await stockItem({
    name: `Milk ${suffix}`,
    itemType: "ingredient",
    unit: "ml",
    quantity: "50",
    unitCost: "20",
  })
  const bottle = await stockItem({
    name: `Bottle ${suffix}`,
    itemType: "merchandise",
    unit: "piece",
    quantity: "5",
    unitCost: "8000",
  })
  const coffee = await createMenuItem({
    name: `Iced coffee ${suffix}`,
    price: "35000",
    productType: "prepared",
  })
  const latte = await createMenuItem({
    name: `Latte ${suffix}`,
    price: "40000",
    productType: "prepared",
  })
  const water = await createMenuItem({
    name: `Water ${suffix}`,
    price: "15000",
    productType: "direct_sale",
  })

  await saveRecipe(page, coffee.code, coffee.name, beans.name, "18")
  await saveRecipe(page, latte.code, latte.name, milk.name, "100")
  await saveRecipe(page, water.code, water.name, bottle.name, "1")

  await page.goto("/pos")
  await page.getByLabel(/Search menu items|Tìm món/).fill(coffee.code)
  await page
    .getByRole("button", { name: new RegExp(`^(Add|Thêm) ${coffee.name}$`) })
    .click()
  await page.getByLabel(/Search menu items|Tìm món/).fill(water.code)
  await page
    .getByRole("button", { name: new RegExp(`^(Add|Thêm) ${water.name}$`) })
    .click()
  await page.getByRole("button", { name: /^(Complete|Hoàn thành đơn)$/ }).click()
  await page.getByRole("button", { name: /Cash|Tiền mặt/ }).click()
  const total = (await page.getByTestId("order-total").innerText()).trim()
  await page
    .getByRole("dialog")
    .getByRole("button", { name: total, exact: true })
    .first()
    .click()
  await page
    .getByRole("button", { name: /Pay and complete|Thu và hoàn thành/ })
    .click()
  const completed = page.getByTestId("order-completed")
  await expect(completed).toBeVisible()
  const orderNumber = (await completed.innerText()).split("·")[0].trim()

  await page.goto("/inventory")
  await page.getByLabel(/Search inventory|Tìm hàng trong kho/).fill(beans.name)
  await expect(
    page.getByRole("cell", { name: "982", exact: true }),
  ).toBeVisible()
  await page.getByLabel(/Search inventory|Tìm hàng trong kho/).fill(bottle.name)
  await expect(page.getByRole("cell", { name: "4", exact: true })).toBeVisible()

  await page.goto("/pos")
  await page.getByLabel(/Search menu items|Tìm món/).fill(latte.code)
  await page
    .getByRole("button", { name: new RegExp(`^(Add|Thêm) ${latte.name}$`) })
    .click()
  await page.getByRole("button", { name: /^(Complete|Hoàn thành đơn)$/ }).click()
  await page.getByRole("button", { name: /Cash|Tiền mặt/ }).click()
  const latteTotal = (await page.getByTestId("order-total").innerText()).trim()
  await page
    .getByRole("dialog")
    .getByRole("button", { name: latteTotal, exact: true })
    .first()
    .click()
  await page
    .getByRole("button", { name: /Pay and complete|Thu và hoàn thành/ })
    .click()
  await expect(page.getByTestId("shortage-dialog")).toBeVisible()
  await expect(page.getByTestId("shortage-dialog")).toContainText(milk.name)
  await page
    .getByTestId("shortage-dialog")
    .locator("[data-slot=button]")
    .click()

  await page.goto("/orders")
  await page.locator("#orders-number").fill(orderNumber)
  await page.getByRole("button", { name: /^(Filter|Lọc)$/ }).click()
  await page
    .getByRole("button", { name: new RegExp(orderNumber) })
    .first()
    .click()
  await page
    .getByRole("button", { name: /Return to stock|Trả hàng vào kho/ })
    .click()
  const returnDialog = page.getByTestId("return-stock-dialog")
  await returnDialog.getByLabel(/Quantity|Số lượng/).fill("1")
  await returnDialog
    .locator("#return-reason")
    .fill("Customer changed their mind")
  await returnDialog
    .getByRole("button", { name: /Return to stock|Trả hàng vào kho/ })
    .click()
  await expect(
    page.getByText(/Stock return recorded|Đã ghi nhận trả hàng/),
  ).toBeVisible()

  await page.goto("/inventory")
  await page.getByLabel(/Search inventory|Tìm hàng trong kho/).fill(bottle.name)
  await expect(page.getByRole("cell", { name: "5", exact: true })).toBeVisible()
})
