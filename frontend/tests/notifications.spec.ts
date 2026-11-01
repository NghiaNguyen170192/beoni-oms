import { expect, type Page, test } from "@playwright/test"
import type { Role } from "../src/client"
import { createCompletedOrder, createMenuItem } from "./utils/api"
import { createUser } from "./utils/privateApi"
import { randomEmail, randomPassword } from "./utils/random"

test.use({ storageState: { cookies: [], origins: [] } })

async function logInOwner(page: Page, email: string, password: string) {
  await page.goto("/login")
  await page.getByTestId("email-input").fill(email)
  await page.getByTestId("password-input").fill(password)
  await page.getByRole("button", { name: "Log In" }).click()
  await page.waitForURL("/")
}

test("owner reviews and changes notification read state", async ({ page }) => {
  const email = randomEmail()
  const password = randomPassword()
  await createUser({ email, password, role: "owner" satisfies Role })
  const item = await createMenuItem({
    name: `Notification item ${Date.now()}`,
    price: "35000",
  })
  const order = await createCompletedOrder(item.id)

  await logInOwner(page, email, password)
  await page.goto("/notifications")

  const row = page.getByTestId(`notification-${order.id}`)
  await expect(row).toBeVisible()
  await expect(row).toContainText(order.number)
  await expect(page.getByTestId("notifications-unread-count")).toContainText(
    "1",
  )

  await page.getByTestId(`notification-toggle-${order.id}`).click()
  await expect(page.getByTestId("notifications-unread-count")).toContainText(
    "0",
  )
  await expect(row).toContainText(/Read|Đã đọc/)

  await page.getByTestId(`notification-toggle-${order.id}`).click()
  await expect(page.getByTestId("notifications-unread-count")).toContainText(
    "1",
  )
  await expect(row).toContainText(/Unread|Chưa đọc/)

  await page.getByTestId(`notification-open-${order.id}`).click()
  await expect(page).toHaveURL(new RegExp(`/orders\\?orderId=${order.id}`))
  await expect(page.getByRole("dialog")).toContainText(order.number)
})

test("non-owner cannot open the notification center", async ({ page }) => {
  const email = randomEmail()
  const password = randomPassword()
  await createUser({ email, password, role: "cashier" satisfies Role })

  await logInOwner(page, email, password)
  await page.goto("/notifications")

  await expect(page).not.toHaveURL(/\/notifications/)
  await expect(
    page.locator("[data-sidebar='sidebar']").getByRole("link", {
      name: "Notifications",
    }),
  ).toHaveCount(0)
})

test("new unread order shows a dismissible toast without marking it read", async ({
  page,
}) => {
  test.setTimeout(40_000)
  const email = randomEmail()
  const password = randomPassword()
  await createUser({ email, password, role: "owner" satisfies Role })
  await logInOwner(page, email, password)
  await page.goto("/notifications")
  await expect(page.getByTestId("notifications-unread-count")).toContainText(
    "0",
  )

  const item = await createMenuItem({
    name: `Toast item ${Date.now()}`,
    price: "35000",
  })
  const order = await createCompletedOrder(item.id)
  const toast = page.locator("[data-sonner-toast]").filter({
    hasText: order.number,
  })
  await expect(toast).toBeVisible({ timeout: 20_000 })
  await toast.getByRole("button", { name: /close/i }).click()
  await expect(toast).toHaveCount(0)

  await page.reload()
  await expect(page.getByTestId("notifications-unread-count")).toContainText(
    "1",
  )
})
