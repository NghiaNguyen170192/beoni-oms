import { useQuery } from "@tanstack/react-query"
import { useMemo, useState } from "react"

import type { MenuItemPublic } from "@/client"
import { CategoryTabs } from "@/components/Catalog/CategoryTabs"
import {
  menuCategoriesQueryOptions,
  menuItemsQueryOptions,
} from "@/components/Catalog/queries"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { useFormatters } from "@/hooks/useBusinessSettings"
import { useI18n } from "@/i18n"
import { mediaUrl } from "@/lib/media"

interface MenuGridProps {
  onAdd: (item: MenuItemPublic) => void
  disabled: boolean
}

export function MenuGrid({ onAdd, disabled }: MenuGridProps) {
  const { t } = useI18n()
  const { formatMoney } = useFormatters()
  const [categoryId, setCategoryId] = useState<string>()
  const [search, setSearch] = useState("")

  const { data: categoryData } = useQuery(menuCategoriesQueryOptions())
  // The whole sellable menu is loaded once and filtered locally for speed.
  const { data: itemData, isPending } = useQuery({
    ...menuItemsQueryOptions({ sellable: true, isActive: true }),
    staleTime: 5 * 60 * 1000,
  })

  const visible = useMemo(() => {
    const term = search.trim().toLowerCase()
    return (itemData?.data ?? []).filter(
      (item) =>
        (!categoryId || item.category_id === categoryId) &&
        (!term ||
          item.name.toLowerCase().includes(term) ||
          item.code.toLowerCase().includes(term)),
    )
  }, [itemData, categoryId, search])

  return (
    <div className="flex flex-col gap-4">
      <Input
        aria-label={t("ordering.menu.searchLabel")}
        placeholder={t("ordering.menu.searchPlaceholder")}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="h-11"
      />
      <CategoryTabs
        categories={categoryData?.data ?? []}
        value={categoryId}
        onChange={setCategoryId}
      />
      {isPending ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
          {Array.from({ length: 8 }).map((_, index) => (
            <Skeleton key={index} className="h-24" />
          ))}
        </div>
      ) : visible.length === 0 ? (
        <p className="py-12 text-center text-muted-foreground">
          {t("ordering.menu.empty")}
        </p>
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
          {visible.map((item) => {
            const src = mediaUrl(item.image_path)
            return (
              <button
                key={item.id}
                type="button"
                disabled={disabled}
                onClick={() => onAdd(item)}
                aria-label={t("ordering.menu.add", { name: item.name })}
                className="flex min-h-24 flex-col items-start justify-between gap-2 rounded-lg border bg-card p-3 text-left transition-colors hover:bg-accent active:scale-[0.98] disabled:opacity-60"
              >
                {src && (
                  <img
                    src={src}
                    alt=""
                    className="h-20 w-full rounded-md object-cover"
                  />
                )}
                <span className="font-medium leading-tight">{item.name}</span>
                <span className="text-sm tabular-nums text-muted-foreground">
                  {formatMoney(item.price)}
                </span>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
