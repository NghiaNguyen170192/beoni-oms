import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import type { ColumnDef } from "@tanstack/react-table"
import { Pencil, Plus, Trash2 } from "lucide-react"
import { useMemo, useState } from "react"

import { CatalogService, type MenuItemPublic } from "@/client"
import { CategoryTabs } from "@/components/Catalog/CategoryTabs"
import { ManageCategories } from "@/components/Catalog/ManageCategories"
import { MenuItemDialog } from "@/components/Catalog/MenuItemDialog"
import {
  menuCategoriesQueryOptions,
  menuItemsQueryOptions,
} from "@/components/Catalog/queries"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
import { DataTable } from "@/components/Common/DataTable"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import useAuth from "@/hooks/useAuth"
import { useFormatters } from "@/hooks/useBusinessSettings"
import useCustomToast from "@/hooks/useCustomToast"
import { t as translate, useI18n } from "@/i18n"
import { PRODUCT_TYPE_LABELS } from "@/lib/labels"
import { mediaUrl } from "@/lib/media"
import { hasPermission, requirePermission } from "@/lib/permissions"
import { handleError } from "@/utils"

export const Route = createFileRoute("/_layout/menu")({
  component: Menu,
  beforeLoad: requirePermission("catalog:view"),
  head: () => ({
    meta: [{ title: `${translate("nav.menu")} - Beoni OMS` }],
  }),
})

function Menu() {
  const { language, t } = useI18n()
  const { user } = useAuth()
  const canManage = hasPermission(user, "catalog:manage")
  const { formatMoney } = useFormatters()
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const [categoryId, setCategoryId] = useState<string>()
  const [search, setSearch] = useState("")
  const [showInactive, setShowInactive] = useState(false)
  const [editingId, setEditingId] = useState<string>()
  const [creating, setCreating] = useState(false)
  const [deleting, setDeleting] = useState<MenuItemPublic>()

  const { data: categoryData } = useQuery(menuCategoriesQueryOptions())
  const categories = categoryData?.data ?? []
  const categoryNames = useMemo(
    () => new Map(categories.map((c) => [c.id, c.name])),
    [categories],
  )

  const { data: itemData, isPending } = useQuery(
    menuItemsQueryOptions({
      q: search.trim(),
      categoryId,
      isActive: canManage && showInactive ? undefined : true,
    }),
  )

  const editing = itemData?.data.find((item) => item.id === editingId)

  const onError = handleError.bind(showErrorToast)
  const invalidateItems = () =>
    queryClient.invalidateQueries({ queryKey: ["menuItems"] })

  const toggle = useMutation({
    mutationFn: ({
      item,
      field,
      value,
    }: {
      item: MenuItemPublic
      field: "is_active" | "is_available"
      value: boolean
    }) =>
      CatalogService.updateItem({
        itemId: item.id,
        requestBody: { [field]: value },
      }),
    onError,
    onSettled: invalidateItems,
  })

  const remove = useMutation({
    mutationFn: (item: MenuItemPublic) =>
      CatalogService.deleteItem({ itemId: item.id }),
    onSuccess: () => {
      showSuccessToast(t("catalog.itemDeleted"))
      setDeleting(undefined)
    },
    onError,
    onSettled: invalidateItems,
  })

  // biome-ignore lint/correctness/useExhaustiveDependencies: `language` re-creates the translated headers
  const columns = useMemo<ColumnDef<MenuItemPublic>[]>(() => {
    const flag = (field: "is_active" | "is_available", label: string) =>
      ({
        id: field,
        header: label,
        cell: ({ row }) => {
          const item = row.original
          if (!canManage) {
            return item[field] ? (
              <Badge variant="secondary">{t("common.yes")}</Badge>
            ) : (
              <Badge variant="outline">{t("common.no")}</Badge>
            )
          }
          return (
            <Checkbox
              aria-label={`${label} ${item.name}`}
              checked={item[field]}
              disabled={toggle.isPending}
              onCheckedChange={(checked) =>
                toggle.mutate({ item, field, value: checked === true })
              }
            />
          )
        },
      }) satisfies ColumnDef<MenuItemPublic>

    const base: ColumnDef<MenuItemPublic>[] = [
      {
        id: "image",
        header: "",
        cell: ({ row }) => {
          const src = mediaUrl(row.original.image_path)
          return src ? (
            <img
              src={src}
              alt=""
              className="size-10 rounded-md object-cover border"
            />
          ) : (
            <div className="size-10 rounded-md border bg-muted" />
          )
        },
      },
      { accessorKey: "code", header: t("catalog.code") },
      {
        accessorKey: "name",
        header: t("common.name"),
        cell: ({ row }) => (
          <span className="font-medium">{row.original.name}</span>
        ),
      },
      {
        id: "category",
        header: t("catalog.category"),
        cell: ({ row }) => categoryNames.get(row.original.category_id) ?? "—",
      },
      {
        id: "type",
        header: t("catalog.type"),
        cell: ({ row }) => t(PRODUCT_TYPE_LABELS[row.original.product_type]),
      },
      {
        id: "price",
        header: () => <div className="text-right">{t("catalog.price")}</div>,
        cell: ({ row }) => (
          <div className="text-right tabular-nums">
            {formatMoney(row.original.price)}
          </div>
        ),
      },
      flag("is_active", t("catalog.active")),
      flag("is_available", t("catalog.available")),
    ]
    if (!canManage) return base
    return [
      ...base,
      {
        id: "actions",
        header: () => <span className="sr-only">{t("common.actions")}</span>,
        cell: ({ row }) => (
          <div className="flex justify-end gap-1">
            <Button
              variant="ghost"
              size="icon"
              aria-label={t("catalog.editItemLabel", {
                name: row.original.name,
              })}
              onClick={() => setEditingId(row.original.id)}
            >
              <Pencil />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              aria-label={t("catalog.deleteItemLabel", {
                name: row.original.name,
              })}
              onClick={() => setDeleting(row.original)}
            >
              <Trash2 />
            </Button>
          </div>
        ),
      },
    ]
  }, [canManage, categoryNames, formatMoney, toggle, language])

  const [deleteBefore, deleteAfter] = t("catalog.deleteItemConfirm").split(
    "{name}",
  )

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{t("nav.menu")}</h1>
          <p className="text-muted-foreground">
            {canManage
              ? t("catalog.descriptionManage")
              : t("catalog.descriptionView")}
          </p>
        </div>
        {canManage && (
          <div className="flex gap-2">
            <ManageCategories />
            <Button onClick={() => setCreating(true)}>
              <Plus className="mr-2" />
              {t("catalog.addItem")}
            </Button>
          </div>
        )}
      </div>

      <CategoryTabs
        categories={categories}
        value={categoryId}
        onChange={setCategoryId}
      />

      <div className="flex flex-wrap items-center gap-4">
        <Input
          aria-label={t("catalog.searchLabel")}
          placeholder={t("catalog.searchPlaceholder")}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-sm"
        />
        {canManage && (
          <div className="flex items-center gap-2">
            <Checkbox
              id="menu-show-inactive"
              checked={showInactive}
              onCheckedChange={(checked) => setShowInactive(checked === true)}
            />
            <Label htmlFor="menu-show-inactive" className="font-normal">
              {t("catalog.showInactive")}
            </Label>
          </div>
        )}
      </div>

      {isPending ? (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 5 }).map((_, index) => (
            <Skeleton key={index} className="h-12 w-full" />
          ))}
        </div>
      ) : (
        <DataTable columns={columns} data={itemData?.data ?? []} />
      )}

      {canManage && (
        <>
          <MenuItemDialog
            open={creating}
            onOpenChange={setCreating}
            categories={categories}
            defaultCategoryId={categoryId}
          />
          <MenuItemDialog
            open={editing !== undefined}
            onOpenChange={(open) => !open && setEditingId(undefined)}
            categories={categories}
            item={editing}
          />
          <ConfirmDialog
            open={deleting !== undefined}
            onOpenChange={(open) => !open && setDeleting(undefined)}
            title={t("catalog.deleteItemTitle")}
            description={
              <>
                {deleteBefore}
                <strong>{deleting?.name}</strong>
                {deleteAfter}
              </>
            }
            confirmLabel={t("common.delete")}
            destructive
            loading={remove.isPending}
            onConfirm={() => deleting && remove.mutate(deleting)}
          />
        </>
      )}
    </div>
  )
}
