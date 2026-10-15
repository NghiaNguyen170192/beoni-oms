import {
  CatalogService,
  LoginService,
  type MenuItemPublic,
  OpenAPI,
  type OrderPublic,
  OrdersService,
  PaymentsService,
} from "../../src/client"
import { firstSuperuser, firstSuperuserPassword } from "../config"

OpenAPI.BASE = `${process.env.VITE_API_URL}`

let token: Promise<string> | null = null

/** Authenticate the shared client as the first superuser (for test setup). */
export async function asSuperuser() {
  token ??= LoginService.loginAccessToken({
    formData: { username: firstSuperuser, password: firstSuperuserPassword },
  }).then((result) => result.access_token)
  const accessToken = await token
  OpenAPI.TOKEN = accessToken
}

export const uniqueSuffix = () =>
  `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`.toUpperCase()

export async function createMenuItem({
  name,
  price,
  productType = "non_stock",
}: {
  name: string
  price: string
  productType?: "prepared" | "direct_sale" | "non_stock"
}): Promise<MenuItemPublic> {
  await asSuperuser()
  const categories = await CatalogService.readCategories({})
  return CatalogService.createItem({
    requestBody: {
      name,
      price,
      category_id: categories.data[0].id,
      product_type: productType,
    },
  })
}

/** Look up a menu item by its (test-unique) name. */
export async function findMenuItem(name: string): Promise<MenuItemPublic> {
  await asSuperuser()
  const result = await CatalogService.readItems({ q: name })
  const item = result.data.find((candidate) => candidate.name === name)
  if (!item) throw new Error(`Menu item ${name} not found`)
  return item
}

export async function createCompletedOrder(
  menuItemId: string,
): Promise<OrderPublic> {
  await asSuperuser()
  const order = await OrdersService.createOrder({
    requestBody: {
      order_type: "counter",
      lines: [{ menu_item_id: menuItemId, quantity: "1" }],
    },
  })
  const methods = await PaymentsService.readPaymentMethods({ activeOnly: true })
  const cash = methods.data.find((method) => method.kind === "cash")
  if (!cash) throw new Error("Cash payment method is not seeded")
  if (Number(order.total) > 0) {
    await PaymentsService.createOrderPayment({
      orderId: order.id,
      idempotencyKey: crypto.randomUUID(),
      requestBody: { method_id: cash.id, amount: order.total },
    })
  }
  return OrdersService.completeOrder({
    orderId: order.id,
    idempotencyKey: crypto.randomUUID(),
  })
}
