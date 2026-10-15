import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import type { ColumnDef } from "@tanstack/react-table"
import { useMemo, useState } from "react"

import { type MenuItemPublic, RecipesService } from "@/client"
import { menuItemsQueryOptions } from "@/components/Catalog/queries"
import { DataTable } from "@/components/Common/DataTable"
import { RecipeVersionDialog } from "@/components/Recipes/RecipeVersionDialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Skeleton } from "@/components/ui/skeleton"
import useAuth from "@/hooks/useAuth"
import { useFormatters } from "@/hooks/useBusinessSettings"
import { type MessageKey, t as translate, useI18n } from "@/i18n"
import { formatNumber } from "@/lib/format"
import { hasPermission, requirePermission } from "@/lib/permissions"

export const Route = createFileRoute("/_layout/recipes")({
  component: Recipes,
  beforeLoad: requirePermission("recipes:read"),
  head: () => ({
    meta: [{ title: `${translate("recipes.title")} - Beoni OMS` }],
  }),
})

function Recipes() {
  const { t } = useI18n()
  const { user } = useAuth()
  const canManage = hasPermission(user, "recipes:manage")
  const [search, setSearch] = useState("")
  const [selected, setSelected] = useState<MenuItemPublic>()

  const { data, isPending } = useQuery(
    menuItemsQueryOptions({ q: search.trim() || undefined }),
  )
  const items = (data?.data ?? []).filter(
    (item) => item.product_type !== "non_stock",
  )

  const columns = useMemo<ColumnDef<MenuItemPublic>[]>(
    () => [
      {
        accessorKey: "name",
        header: () => translate("common.name"),
        cell: ({ row }) => (
          <button
            type="button"
            className="text-left font-medium hover:underline"
            onClick={() => setSelected(row.original)}
          >
            {row.original.name}
          </button>
        ),
      },
      {
        accessorKey: "code",
        header: () => translate("catalog.code"),
      },
      {
        id: "type",
        enableSorting: false,
        header: () => translate("catalog.type"),
        cell: ({ row }) =>
          translate(`productType.${row.original.product_type}` as MessageKey),
      },
    ],
    [],
  )

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          {t("recipes.title")}
        </h1>
        <p className="text-muted-foreground">{t("recipes.description")}</p>
      </div>
      <Input
        aria-label={t("recipes.search")}
        data-testid="recipes-search"
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        placeholder={t("recipes.search")}
        className="max-w-sm"
      />
      {isPending ? (
        <Skeleton className="h-40" />
      ) : items.length === 0 ? (
        <p className="text-muted-foreground">{t("recipes.empty")}</p>
      ) : (
        <DataTable columns={columns} data={items} />
      )}
      <RecipeSheet
        item={selected}
        canManage={canManage}
        onClose={() => setSelected(undefined)}
      />
    </div>
  )
}

function RecipeSheet({
  item,
  canManage,
  onClose,
}: {
  item: MenuItemPublic | undefined
  canManage: boolean
  onClose: () => void
}) {
  const { t } = useI18n()
  const { formatMoney, formatDateTime } = useFormatters()
  const [editing, setEditing] = useState(false)
  const [pickedId, setPickedId] = useState<string>()

  const versions = useQuery({
    queryKey: ["recipes", item?.id],
    queryFn: () => RecipesService.readRecipes({ menuItemId: item!.id }),
    enabled: item !== undefined,
  })
  const rows = versions.data?.data ?? []
  const picked = rows.find((row) => row.id === pickedId) ?? rows[0]

  const preview = useQuery({
    queryKey: ["recipe-cost", picked?.id],
    queryFn: () => RecipesService.readCostPreview({ recipeId: picked!.id }),
    enabled: picked !== undefined,
  })

  return (
    <Sheet
      open={item !== undefined}
      onOpenChange={(open) => {
        if (!open) {
          setPickedId(undefined)
          onClose()
        }
      }}
    >
      <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
        {item && (
          <>
            <SheetHeader>
              <SheetTitle>{item.name}</SheetTitle>
              <SheetDescription>
                {item.code} ·{" "}
                {t(`productType.${item.product_type}` as MessageKey)}
              </SheetDescription>
            </SheetHeader>
            <div className="flex flex-col gap-4 px-4 pb-6">
              {canManage && (
                <Button className="w-fit" onClick={() => setEditing(true)}>
                  {t("recipes.newVersion")}
                </Button>
              )}
              {versions.isPending ? (
                <Skeleton className="h-24" />
              ) : rows.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  {t("recipes.noVersions")}
                </p>
              ) : (
                rows.map((version) => (
                  <button
                    key={version.id}
                    type="button"
                    className="rounded-md border p-3 text-left"
                    onClick={() => setPickedId(version.id)}
                  >
                    <div className="flex items-center gap-2">
                      <span className="font-medium">v{version.version}</span>
                      <Badge variant="secondary">
                        {t(`recipes.kind.${version.kind}` as MessageKey)}
                      </Badge>
                      {picked?.id === version.id && (
                        <Badge>{t("recipes.versions")}</Badge>
                      )}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {formatDateTime(version.effective_from)}
                    </div>
                    <ul className="mt-2 text-sm">
                      {version.lines.map((line) => (
                        <li key={line.id}>
                          {line.item_name} · {formatNumber(line.quantity)}{" "}
                          {t(`unit.${line.base_unit}` as MessageKey)}
                        </li>
                      ))}
                    </ul>
                  </button>
                ))
              )}
              {preview.data && (
                <div className="rounded-md bg-muted p-3">
                  <div className="text-sm text-muted-foreground">
                    {t("recipes.cost")} · {t("recipes.perServing")}
                  </div>
                  <div className="text-lg font-semibold tabular-nums">
                    {formatMoney(preview.data.estimated_cost)}
                  </div>
                  {preview.data.lines
                    .filter((line) => line.cost_unknown)
                    .map((line) => (
                      <div key={line.inventory_item_id} className="text-sm">
                        {line.item_name}: {t("recipes.costUnknown")}
                      </div>
                    ))}
                </div>
              )}
            </div>
            {editing && (
              <RecipeVersionDialog
                menuItemId={item.id}
                productType={item.product_type}
                latest={rows[0]}
                open={editing}
                onOpenChange={setEditing}
                onSaved={(recipe) => {
                  setPickedId(recipe.id)
                  versions.refetch()
                }}
              />
            )}
          </>
        )}
      </SheetContent>
    </Sheet>
  )
}
