import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import type { ColumnDef } from "@tanstack/react-table"
import { Boxes, History, Pencil, Plus } from "lucide-react"
import { useMemo, useState } from "react"

import type { InventoryItemPublic } from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import { FinishedGoodLots } from "@/components/Inventory/FinishedGoodLots"
import { InventoryItemDialog } from "@/components/Inventory/InventoryItemDialog"
import { MovementHistory } from "@/components/Inventory/MovementHistory"
import {
  type InventoryItemFilters,
  inventoryCategoriesQueryOptions,
  inventoryItemsQueryOptions,
} from "@/components/Inventory/queries"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import useAuth from "@/hooks/useAuth"
import { useFormatters } from "@/hooks/useBusinessSettings"
import { t as translate, useI18n } from "@/i18n"
import { formatNumber } from "@/lib/format"
import { UNIT_LABELS } from "@/lib/labels"
import { hasPermission, requirePermission } from "@/lib/permissions"
import badgeStyles from "@/styles/badge.module.css"

export const Route = createFileRoute("/_layout/inventory")({
  component: Inventory,
  beforeLoad: requirePermission("inventory:view"),
  head: () => ({
    meta: [{ title: `${translate("inventory.title")} - Beoni OMS` }],
  }),
})

const ALL = "all"
type StatusFilter = typeof ALL | "active" | "inactive"
type StockFilter = typeof ALL | "low" | "negative"

function Inventory() {
  const { t } = useI18n()
  const { user } = useAuth()
  const canManage = hasPermission(user, "inventory:manage")
  const { formatMoney, formatUnitCost } = useFormatters()

  const [search, setSearch] = useState("")
  const [categoryId, setCategoryId] = useState<string>()
  const [status, setStatus] = useState<StatusFilter>("active")
  const [stock, setStock] = useState<StockFilter>(ALL)
  const [creating, setCreating] = useState(false)
  const [editingId, setEditingId] = useState<string>()
  const [historyId, setHistoryId] = useState<string>()
  const [lotsId, setLotsId] = useState<string>()

  const filters: InventoryItemFilters = {
    q: search.trim(),
    categoryId,
    isActive: status === ALL ? undefined : status === "active",
    lowStock: stock === "low" || undefined,
    negativeStock: stock === "negative" || undefined,
  }

  const { data: categoryData } = useQuery(inventoryCategoriesQueryOptions())
  const categories = categoryData?.data ?? []
  const categoryNames = useMemo(
    () => new Map(categories.map((c) => [c.id, c.name])),
    [categories],
  )
  const { data, isPending } = useQuery(inventoryItemsQueryOptions(filters))
  const items = data?.data ?? []
  const editing = items.find((item) => item.id === editingId)
  const history = items.find((item) => item.id === historyId)
  const lotsItem = items.find((item) => item.id === lotsId)

  const columns = useMemo<ColumnDef<InventoryItemPublic>[]>(
    () => [
      { accessorKey: "sku", header: () => translate("inventory.field.sku") },
      {
        accessorKey: "name",
        header: () => translate("inventory.field.name"),
        cell: ({ row }) => (
          <span className="font-medium">{row.original.name}</span>
        ),
      },
      {
        id: "category",
        accessorFn: (row) => categoryNames.get(row.category_id) ?? "",
        header: () => translate("inventory.field.category"),
        cell: ({ row }) => categoryNames.get(row.original.category_id) ?? "—",
      },
      {
        id: "quantity",
        accessorFn: (row) => Number(row.quantity),
        header: () => (
          <div className="text-right">
            {translate("inventory.field.quantity")}
          </div>
        ),
        cell: ({ row }) => (
          <div className="text-right tabular-nums">
            {formatNumber(row.original.quantity)}
          </div>
        ),
      },
      {
        accessorKey: "base_unit",
        header: () => translate("inventory.field.unit"),
        cell: ({ row }) => translate(UNIT_LABELS[row.original.base_unit]),
      },
      {
        id: "avg_unit_cost",
        accessorFn: (row) => Number(row.avg_unit_cost),
        header: () => (
          <div className="text-right">
            {translate("inventory.field.avgCost")}
          </div>
        ),
        cell: ({ row }) => (
          <div className="text-right tabular-nums">
            {formatUnitCost(row.original.avg_unit_cost)}
          </div>
        ),
      },
      {
        id: "value",
        accessorFn: (row) => Number(row.value),
        header: () => (
          <div className="text-right">{translate("inventory.field.value")}</div>
        ),
        cell: ({ row }) => (
          <div className="text-right tabular-nums">
            {formatMoney(row.original.value)}
          </div>
        ),
      },
      {
        id: "status",
        enableSorting: false,
        header: () => translate("common.status"),
        cell: ({ row }) => (
          <div className="flex flex-wrap gap-1">
            {row.original.is_negative_stock && (
              <Badge variant="destructive">
                {translate("inventory.negativeStock")}
              </Badge>
            )}
            {row.original.is_low_stock && !row.original.is_negative_stock && (
              <Badge className="bg-amber-500 text-white">
                {translate("inventory.lowStock")}
              </Badge>
            )}
            {!row.original.is_active && (
              <Badge className={badgeStyles.red}>
                {translate("inventory.status.inactive")}
              </Badge>
            )}
          </div>
        ),
      },
      {
        id: "actions",
        enableSorting: false,
        header: () => (
          <span className="sr-only">{translate("common.actions")}</span>
        ),
        cell: ({ row }) => (
          <div className="flex justify-end gap-1">
            {row.original.role === "finished_good" && (
              <Button
                variant="ghost"
                size="icon"
                aria-label={translate("inventory.lots.forItem", {
                  name: row.original.name,
                })}
                onClick={() => setLotsId(row.original.id)}
              >
                <Boxes />
              </Button>
            )}
            <Button
              variant="ghost"
              size="icon"
              aria-label={translate("inventory.movementsFor", {
                sku: row.original.sku,
              })}
              onClick={() => setHistoryId(row.original.id)}
            >
              <History />
            </Button>
            {canManage && (
              <Button
                variant="ghost"
                size="icon"
                aria-label={translate("inventory.editFor", {
                  sku: row.original.sku,
                })}
                onClick={() => setEditingId(row.original.id)}
              >
                <Pencil />
              </Button>
            )}
          </div>
        ),
      },
    ],
    [canManage, categoryNames, formatMoney, formatUnitCost],
  )

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            {t("inventory.title")}
          </h1>
          <p className="text-muted-foreground">{t("inventory.description")}</p>
        </div>
        {canManage && (
          <Button onClick={() => setCreating(true)}>
            <Plus className="mr-2" />
            {t("inventory.addItem")}
          </Button>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Input
          aria-label={t("inventory.searchLabel")}
          placeholder={t("inventory.searchPlaceholder")}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-xs"
        />
        <Select
          value={categoryId ?? ALL}
          onValueChange={(value) =>
            setCategoryId(value === ALL ? undefined : value)
          }
        >
          <SelectTrigger
            className="w-48"
            aria-label={t("inventory.categoryFilter")}
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>{t("inventory.allCategories")}</SelectItem>
            {categories.map((category) => (
              <SelectItem key={category.id} value={category.id}>
                {category.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          value={status}
          onValueChange={(value) => setStatus(value as StatusFilter)}
        >
          <SelectTrigger
            className="w-48"
            aria-label={t("inventory.statusFilter")}
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="active">
              {t("inventory.status.active")}
            </SelectItem>
            <SelectItem value="inactive">
              {t("inventory.status.inactive")}
            </SelectItem>
            <SelectItem value={ALL}>{t("inventory.allStatuses")}</SelectItem>
          </SelectContent>
        </Select>
        <Select
          value={stock}
          onValueChange={(value) => setStock(value as StockFilter)}
        >
          <SelectTrigger
            className="w-56"
            aria-label={t("inventory.stockFilter")}
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>{t("inventory.allStockLevels")}</SelectItem>
            <SelectItem value="low">{t("inventory.lowStock")}</SelectItem>
            <SelectItem value="negative">
              {t("inventory.negativeStock")}
            </SelectItem>
          </SelectContent>
        </Select>
      </div>

      {isPending ? (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 5 }).map((_, index) => (
            <Skeleton key={index} className="h-12 w-full" />
          ))}
        </div>
      ) : (
        <DataTable columns={columns} data={items} />
      )}

      {canManage && (
        <>
          <InventoryItemDialog
            open={creating}
            onOpenChange={setCreating}
            categories={categories}
          />
          <InventoryItemDialog
            open={editing !== undefined}
            onOpenChange={(open) => !open && setEditingId(undefined)}
            categories={categories}
            item={editing}
          />
        </>
      )}
      <MovementHistory item={history} onClose={() => setHistoryId(undefined)} />
      <FinishedGoodLots item={lotsItem} onClose={() => setLotsId(undefined)} />
    </div>
  )
}
