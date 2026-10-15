import { expect, type Page, test } from "@playwright/test"
import { uniqueSuffix } from "./utils/api"

async function postAdjustment(
  page: Page,
  {
    label,
    reason,
    amount,
    unitCost,
    note,
  }: {
    label: string
    reason: string
    amount: string
    unitCost?: string
    note: string
  },
) {
  await page.goto("/stock-adjustments")
  await page.getByRole("button", { name: "New Adjustment" }).click()
  const dialog = page.getByRole("dialog")
  await dialog.getByLabel("Item for line 1").click()
  await page.getByRole("option", { name: label }).click()
  await dialog.getByLabel("Reason for line 1").click()
  await page.getByRole("option", { name: reason, exact: true }).click()
  await dialog
    .getByLabel(/Quantity removed|Change|Counted quantity/)
    .fill(amount)
  if (unitCost) {
    await dialog.getByLabel("Unit cost").fill(unitCost)
  }
  await dialog.getByLabel("Note").fill(note)
  await dialog.getByRole("button", { name: "Review" }).click()
  await page.getByRole("button", { name: "Post", exact: true }).click()
  await expect(page.getByText(/Adjustment #\d+ posted/)).toBeVisible()
}

test("Inventory item lifecycle: create, spoil, see movement and low stock, reverse", async ({
  page,
}) => {
  const suffix = uniqueSuffix()
  const name = `E2E Sữa tươi ${suffix}`

  await page.goto("/inventory")
  await expect(page.getByRole("heading", { name: "Inventory" })).toBeVisible()
  await page.getByRole("button", { name: "Add Item" }).click()
  const form = page.getByRole("dialog")
  await expect(form.getByLabel("SKU")).toHaveCount(0)
  await form.getByLabel("Item name").fill(name)
  await form.getByLabel("Category").click()
  await page.getByRole("option", { name: "Nguyên vật liệu" }).click()
  await form.getByLabel("Base unit", { exact: true }).click()
  await page.getByRole("option", { name: "ml", exact: true }).click()
  await form.getByLabel("Purchase unit", { exact: true }).click()
  await page.getByRole("option", { name: "l", exact: true }).click()
  await form.getByLabel("Base units per purchase unit").fill("1000")
  await form.getByLabel("Minimum stock").fill("100")
  await form.getByRole("button", { name: "Save" }).click()
  await expect(page.getByText("Item created")).toBeVisible()

  await page.getByLabel("Search inventory").fill(name)
  const row = page.getByRole("row").filter({ hasText: name })
  await expect(row).toHaveCount(1)
  const sku = (await row.getByRole("cell").first().innerText()).trim()
  expect(sku).toMatch(/^SP-\d{5}$/)
  const label = `${sku} · ${name}`

  await row.getByRole("button", { name: `Edit ${sku}` }).click()
  const editForm = page.getByRole("dialog")
  await expect(editForm.getByLabel("SKU")).toHaveValue(sku)
  await expect(editForm.getByLabel("SKU")).not.toBeEditable()
  await page.keyboard.press("Escape")

  await postAdjustment(page, {
    label,
    reason: "Correction",
    amount: "500",
    unitCost: "30",
    note: `opening ${suffix}`,
  })
  await postAdjustment(page, {
    label,
    reason: "Spoilage",
    amount: "450",
    note: `spoiled ${suffix}`,
  })

  await page.goto("/inventory")
  await page.getByLabel("Search inventory").fill(name)
  await expect(row).toContainText(sku)
  await expect(row).toContainText("50")
  await expect(row.getByText("Below minimum stock")).toBeVisible()

  await row.getByRole("button", { name: `Movements ${sku}` }).click()
  const drawer = page.getByRole("dialog")
  await expect(drawer.getByRole("row")).toHaveCount(3)
  await expect(drawer.getByRole("row").nth(1)).toContainText("450")
  await expect(drawer.getByRole("row").nth(2)).toContainText("+500")
  await page.keyboard.press("Escape")

  await page.goto("/stock-adjustments")
  const spoilage = page
    .getByRole("row")
    .filter({ hasText: `spoiled ${suffix}` })
  await spoilage.getByRole("button", { name: "Reverse" }).click()
  await page.getByLabel("Reason").fill("Counted wrong")
  await page.getByRole("button", { name: "Reverse", exact: true }).click()
  await expect(page.getByText(/Adjustment #\d+ reversed/)).toBeVisible()
  await expect(spoilage).toContainText("Reversed")
  await expect(spoilage.getByRole("button", { name: "Reverse" })).toHaveCount(0)

  await page.goto("/inventory")
  await page.getByLabel("Search inventory").fill(name)
  await expect(row).toContainText("500")
  await expect(row.getByText("Below minimum stock")).toHaveCount(0)
})
