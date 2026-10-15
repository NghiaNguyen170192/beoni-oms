import { expect, type Page, test } from "@playwright/test"
import { uniqueSuffix } from "./utils/api"

const en = {
  inventory: "Inventory",
  addItem: "Add Item",
  itemName: "Item name",
  category: "Category",
  baseUnit: "Base unit",
  purchaseUnit: "Purchase unit",
  factor: "Base units per purchase unit",
  save: "Save",
  itemCreated: "Item created",
  searchInventory: "Search inventory",
  suppliers: "Suppliers",
  addSupplier: "Add Supplier",
  supplierName: "Supplier name",
  phone: "Phone",
  supplierCreated: "Supplier created",
  searchSuppliers: "Search suppliers",
  newReceipt: "New Receipt",
  supplier: "Supplier",
  searchItems: "Search items",
  item: "Item",
  quantity: "Purchase quantity",
  cost: "Cost per purchase unit",
  preview: /Preview/,
  draftSaved: "Draft saved",
  post: "Post",
  postTitle: "Post this receipt?",
  posted: /posted/,
  searchReference: "Search by reference",
  reverse: "Reverse",
  reverseTitle: "Reverse this receipt?",
  reason: "Reason",
  reversed: /reversed/,
}

const vi = {
  inventory: "Kho hàng",
  addItem: "Thêm hàng hóa",
  itemName: "Tên hàng",
  category: "Nhóm hàng",
  baseUnit: "Đơn vị tính",
  purchaseUnit: "Đơn vị nhập",
  factor: "Hệ số quy đổi",
  save: "Lưu",
  itemCreated: "Đã thêm hàng hóa",
  searchInventory: "Tìm hàng trong kho",
  suppliers: "Nhà cung cấp",
  addSupplier: "Thêm nhà cung cấp",
  supplierName: "Tên nhà cung cấp",
  phone: "Điện thoại",
  supplierCreated: "Đã thêm nhà cung cấp",
  searchSuppliers: "Tìm nhà cung cấp",
  newReceipt: "Phiếu nhập mới",
  supplier: "Nhà cung cấp",
  searchItems: "Tìm mặt hàng",
  item: "Mặt hàng",
  quantity: "Số lượng mua",
  cost: "Đơn giá theo đơn vị mua",
  preview: /Tạm tính/,
  draftSaved: "Đã lưu nháp",
  post: "Ghi sổ",
  postTitle: "Ghi sổ phiếu này?",
  posted: /Đã ghi sổ phiếu/,
  searchReference: "Tìm theo số phiếu",
  reverse: "Đảo phiếu",
  reverseTitle: "Đảo phiếu này?",
  reason: "Lý do",
  reversed: /Đã đảo phiếu/,
}

async function labels(page: Page) {
  const settings = page.waitForResponse(
    (response) => response.url().includes("/api/v1/settings") && response.ok(),
  )
  await page.goto("/inventory")
  await settings
  const heading = page.getByRole("heading", {
    name: new RegExp(`^(${en.inventory}|${vi.inventory})$`),
  })
  await expect(heading).toBeVisible()
  const text = (await heading.innerText()).trim()
  return text === vi.inventory ? vi : en
}

test("create a supplier, post a receipt, then reverse it", async ({ page }) => {
  test.setTimeout(60_000)
  const suffix = uniqueSuffix()
  const supplierName = `E2E NCC ${suffix}`
  const itemName = `E2E Cà phê ${suffix}`
  const L = await labels(page)

  await expect(page.getByRole("heading", { name: L.inventory })).toBeVisible()
  await page.getByRole("button", { name: L.addItem }).click()
  const itemForm = page.getByRole("dialog")
  await itemForm.getByLabel(L.itemName).fill(itemName)
  await itemForm.getByLabel(L.category).click()
  await page.getByRole("option", { name: "Nguyên vật liệu" }).click()
  await itemForm.getByLabel(L.baseUnit, { exact: true }).click()
  await page.getByRole("option", { name: "g", exact: true }).click()
  await itemForm.getByLabel(L.purchaseUnit, { exact: true }).click()
  await page.getByRole("option", { name: "kg", exact: true }).click()
  await itemForm.getByLabel(L.factor).fill("1000")
  await itemForm.getByRole("button", { name: L.save }).click()
  await expect(page.getByText(L.itemCreated)).toBeVisible()

  await page.goto("/suppliers")
  await expect(page.getByRole("heading", { name: L.suppliers })).toBeVisible()
  await page.getByRole("button", { name: L.addSupplier }).click()
  const supplierForm = page.getByRole("dialog")
  await supplierForm.getByLabel(L.supplierName).fill(supplierName)
  await supplierForm.getByLabel(L.phone).fill("0901000111")
  await supplierForm.getByRole("button", { name: L.save }).click()
  await expect(page.getByText(L.supplierCreated)).toBeVisible()

  await page.goto("/stock-receipts")
  await page.getByRole("button", { name: L.newReceipt }).click()
  const receiptForm = page.getByRole("dialog")
  await receiptForm.getByLabel(L.supplier, { exact: true }).click()
  await page.getByRole("option", { name: supplierName }).click()
  await receiptForm.getByLabel(`${L.item} 1`).click()
  const itemList = page.locator("[data-radix-select-viewport]")
  await itemList.evaluate((node) => {
    node.scrollTop = node.scrollHeight
  })
  const searchBox = await page.getByLabel(L.searchItems).boundingBox()
  const popupBox = await page.locator("[data-slot=select-content]").boundingBox()
  const listBox = await itemList.boundingBox()
  if (!searchBox || !popupBox || !listBox) {
    throw new Error("item dropdown search is not visible")
  }
  expect(searchBox.y).toBeLessThan(listBox.y)
  expect(searchBox.y - popupBox.y).toBeLessThan(12)
  await page.getByLabel(L.searchItems).fill(itemName)
  await page.getByRole("option", { name: new RegExp(itemName) }).click()
  await receiptForm.getByLabel(`${L.quantity} 1`).fill("1")
  await receiptForm.getByLabel(`${L.cost} 1`).fill("1000")
  await expect(receiptForm.getByText(L.preview)).toBeVisible()
  await receiptForm.getByRole("button", { name: L.save }).click()
  await expect(page.getByText(L.draftSaved)).toBeVisible()

  const row = page.getByRole("row").filter({ hasText: supplierName })
  const reference = (await row.getByRole("cell").first().innerText()).trim()
  await row.getByRole("button", { name: reference }).click()
  await page.getByRole("button", { name: L.post, exact: true }).click()
  const postDialog = page.getByRole("dialog", { name: L.postTitle })
  await postDialog.getByRole("button", { name: L.post, exact: true }).click()
  await expect(page.getByText(L.posted)).toBeVisible()

  await page.goto("/inventory")
  await page.getByLabel(L.searchInventory).fill(itemName)
  const itemRow = page.getByRole("row").filter({ hasText: itemName })
  await expect(itemRow).toContainText("1.000")

  await page.goto("/suppliers")
  await page.getByLabel(L.searchSuppliers).fill(supplierName)
  await page.getByRole("button", { name: supplierName, exact: true }).click()
  await expect(page.getByText("1.000 ₫").first()).toBeVisible()

  await page.goto("/stock-receipts")
  await page.getByLabel(L.searchReference).fill(reference)
  const posted = page.getByRole("row").filter({ hasText: reference })
  await posted.getByRole("button", { name: reference }).click()
  await page.getByRole("button", { name: L.reverse }).click()
  await page.getByLabel(L.reason).fill("Wrong delivery")
  const reverseDialog = page.getByRole("dialog", { name: L.reverseTitle })
  await reverseDialog.getByRole("button", { name: L.reverse }).click()
  await expect(page.getByText(L.reversed)).toBeVisible()

  await page.goto("/inventory")
  await page.getByLabel(L.searchInventory).fill(itemName)
  await expect(
    page.getByRole("row").filter({ hasText: itemName }),
  ).toContainText("0")
})
