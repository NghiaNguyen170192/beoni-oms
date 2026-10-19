import {
  InventoryService,
  type ItemType,
  type MovementType,
  OpenAPI,
} from "@/client"
import { request } from "@/client/core/request"

export type FinishedGoodLot = {
  id: string
  lot_number: string
  origin: "production" | "opening_stock"
  batch_id: string | null
  batch_number: number | null
  inventory_item_id: string
  produced_quantity: string
  quantity_on_hand: string
  reserved_quantity: string
  available_quantity: string
  unit_cost: string | null
  finished_at: string
  expiry_date: string | null
}

type FinishedGoodLotsPublic = {
  data: FinishedGoodLot[]
  count: number
}

export type InventoryItemFilters = {
  q?: string
  categoryId?: string
  itemType?: ItemType
  isActive?: boolean
  lowStock?: boolean
  negativeStock?: boolean
}

export const inventoryCategoriesQueryOptions = () => ({
  queryKey: ["inventoryCategories"],
  queryFn: () => InventoryService.readCategories(),
  staleTime: 5 * 60 * 1000,
})

export const inventoryItemsQueryOptions = (filters: InventoryItemFilters) => ({
  queryKey: ["inventoryItems", filters],
  queryFn: () =>
    InventoryService.readItems({
      q: filters.q || undefined,
      categoryId: filters.categoryId,
      itemType: filters.itemType,
      isActive: filters.isActive,
      lowStock: filters.lowStock,
      negativeStock: filters.negativeStock,
      limit: 500,
    }),
})

export const movementsQueryOptions = (
  itemId: string,
  movementType: MovementType | undefined,
) => ({
  queryKey: ["inventoryMovements", itemId, movementType],
  queryFn: () =>
    InventoryService.readItemMovements({ itemId, movementType, limit: 200 }),
})

export const finishedGoodLotsQueryOptions = (itemId: string) => ({
  queryKey: ["finishedGoodLots", itemId],
  queryFn: () =>
    request<FinishedGoodLotsPublic>(OpenAPI, {
      method: "GET",
      url: "/api/v1/inventory/items/{item_id}/lots",
      path: { item_id: itemId },
    }),
})

/** "12.5000" -> "12.5" for editing; the backend re-quantizes on save. */
export function editableQuantity(value: string): string {
  return value.includes(".") ? value.replace(/\.?0+$/, "") : value
}
