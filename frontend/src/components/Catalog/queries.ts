import { CatalogService, type ProductType } from "@/client"

export type MenuItemFilters = {
  q?: string
  categoryId?: string
  productType?: ProductType
  /** `undefined` lists active and inactive items (managers only). */
  isActive?: boolean
  sellable?: boolean
}

export const menuCategoriesQueryOptions = (includeInactive = false) => ({
  queryKey: ["menuCategories", { includeInactive }],
  queryFn: () => CatalogService.readCategories({ includeInactive }),
  staleTime: 5 * 60 * 1000,
})

export const menuItemsQueryOptions = (filters: MenuItemFilters) => ({
  queryKey: ["menuItems", filters],
  queryFn: () =>
    CatalogService.readItems({
      q: filters.q || undefined,
      categoryId: filters.categoryId,
      productType: filters.productType,
      isActive: filters.isActive,
      sellable: filters.sellable,
      limit: 500,
    }),
})

/** "29000.00" -> "29000" for editing; the backend re-quantizes on save. */
export function editableAmount(value: string): string {
  return value.replace(/\.0+$/, "")
}
