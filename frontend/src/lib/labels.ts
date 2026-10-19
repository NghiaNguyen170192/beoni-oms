import type {
  AdjustmentReason,
  DiscountType,
  InventoryRole,
  ItemType,
  MovementType,
  OrderStatus,
  OrderType,
  ProductType,
  Unit,
} from "@/client"
import type { MessageKey } from "@/i18n"

// The *_LABELS maps hold message keys; render them with `t(LABELS[value])`.

export const PRODUCT_TYPES = [
  "prepared",
  "direct_sale",
  "non_stock",
] as const satisfies readonly ProductType[]

export const PRODUCT_TYPE_LABELS = {
  prepared: "productType.prepared",
  direct_sale: "productType.direct_sale",
  non_stock: "productType.non_stock",
} as const satisfies Record<ProductType, MessageKey>

export const ITEM_TYPES = [
  "ingredient",
  "merchandise",
  "packaging",
  "consumable",
] as const satisfies readonly ItemType[]

export const ITEM_TYPE_LABELS = {
  ingredient: "itemType.ingredient",
  merchandise: "itemType.merchandise",
  packaging: "itemType.packaging",
  consumable: "itemType.consumable",
} as const satisfies Record<ItemType, MessageKey>

export const INVENTORY_ROLES = [
  "raw_material",
  "finished_good",
  "general",
] as const satisfies readonly InventoryRole[]

export const INVENTORY_ROLE_LABELS = {
  raw_material: "inventory.role.rawMaterial",
  finished_good: "inventory.role.finishedGood",
  general: "inventory.role.general",
} as const satisfies Record<InventoryRole, MessageKey>

export const UNITS = [
  "g",
  "kg",
  "ml",
  "l",
  "piece",
  "pack",
  "bottle",
  "cup",
  "box",
] as const satisfies readonly Unit[]

export const UNIT_LABELS = {
  g: "unit.g",
  kg: "unit.kg",
  ml: "unit.ml",
  l: "unit.l",
  piece: "unit.piece",
  pack: "unit.pack",
  bottle: "unit.bottle",
  cup: "unit.cup",
  box: "unit.box",
} as const satisfies Record<Unit, MessageKey>

export const MOVEMENT_TYPE_LABELS = {
  receipt: "movementType.receipt",
  sale_consumption: "movementType.sale_consumption",
  production_consumption: "movementType.production_consumption",
  production_receipt: "movementType.production_receipt",
  adjustment: "movementType.adjustment",
  return: "movementType.return",
  reversal: "movementType.reversal",
} as const satisfies Record<MovementType, MessageKey>

export const ADJUSTMENT_REASONS = [
  "physical_count",
  "spoilage",
  "expired",
  "damaged",
  "missing",
  "correction",
] as const satisfies readonly AdjustmentReason[]

export const ADJUSTMENT_REASON_LABELS = {
  physical_count: "adjustmentReason.physical_count",
  spoilage: "adjustmentReason.spoilage",
  expired: "adjustmentReason.expired",
  damaged: "adjustmentReason.damaged",
  missing: "adjustmentReason.missing",
  correction: "adjustmentReason.correction",
} as const satisfies Record<AdjustmentReason, MessageKey>

/** Reasons that may only decrease stock (mirrors the backend rule). */
export const DECREASE_REASONS: readonly AdjustmentReason[] = [
  "spoilage",
  "expired",
  "damaged",
  "missing",
]

export const ORDER_TYPES = [
  "counter",
  "takeaway",
  "dine_in",
] as const satisfies readonly OrderType[]

export const ORDER_TYPE_LABELS = {
  counter: "orderType.counter",
  takeaway: "orderType.takeaway",
  dine_in: "orderType.dine_in",
} as const satisfies Record<OrderType, MessageKey>

export const ORDER_STATUSES = [
  "draft",
  "confirmed",
  "paid",
  "completed",
  "cancelled",
  "partially_refunded",
  "refunded",
] as const satisfies readonly OrderStatus[]

export const ORDER_STATUS_LABELS = {
  draft: "orderStatus.draft",
  confirmed: "orderStatus.confirmed",
  paid: "orderStatus.paid",
  completed: "orderStatus.completed",
  cancelled: "orderStatus.cancelled",
  partially_refunded: "orderStatus.partially_refunded",
  refunded: "orderStatus.refunded",
} as const satisfies Record<OrderStatus, MessageKey>

export const DISCOUNT_TYPE_LABELS = {
  amount: "discountType.amount",
  percent: "discountType.percent",
} as const satisfies Record<DiscountType, MessageKey>
