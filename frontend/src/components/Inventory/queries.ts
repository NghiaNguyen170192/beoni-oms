import { InventoryService, type ItemType, type MovementType } from "@/client"

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

/** "12.5000" -> "12.5" for editing; the backend re-quantizes on save. */
export function editableQuantity(value: string): string {
  return value.includes(".") ? value.replace(/\.?0+$/, "") : value
}
