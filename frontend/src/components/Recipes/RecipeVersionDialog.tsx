import { useMutation, useQuery } from "@tanstack/react-query"
import { type FormEvent, useState } from "react"

import {
  type ApiError,
  InventoryService,
  type ProductType,
  type RecipePublic,
  RecipesService,
  type Unit,
} from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { type MessageKey, useI18n } from "@/i18n"
import { handleError } from "@/utils"

type DraftLine = {
  inventory_item_id: string
  item_name: string
  item_sku: string
  base_unit: Unit
  quantity: string
}

function localDateTimeValue(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, "0")
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function fromVersion(version: RecipePublic | undefined): DraftLine[] {
  return (
    version?.lines.map((line) => ({
      inventory_item_id: line.inventory_item_id,
      item_name: line.item_name,
      item_sku: line.item_sku,
      base_unit: line.base_unit,
      quantity: line.quantity.replace(/\.?0+$/, ""),
    })) ?? []
  )
}

export function RecipeVersionDialog({
  menuItemId,
  productType,
  latest,
  open,
  onOpenChange,
  onSaved,
}: {
  menuItemId: string
  productType: ProductType
  latest: RecipePublic | undefined
  open: boolean
  onOpenChange: (open: boolean) => void
  onSaved: (recipe: RecipePublic) => void
}) {
  const { t } = useI18n()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [effectiveFrom, setEffectiveFrom] = useState(() =>
    localDateTimeValue(new Date()),
  )
  const [lines, setLines] = useState<DraftLine[]>(() => fromVersion(latest))
  const [search, setSearch] = useState("")

  const matches = useQuery({
    queryKey: ["inventoryItems", "recipe-search", search],
    queryFn: () =>
      InventoryService.readItems({
        q: search.trim(),
        isActive: true,
        limit: 8,
      }),
    enabled: open && search.trim().length > 0,
  })

  const save = useMutation({
    mutationFn: () =>
      RecipesService.createRecipeVersion({
        requestBody: {
          menu_item_id: menuItemId,
          effective_from: new Date(effectiveFrom).toISOString(),
          lines: lines.map((line) => ({
            inventory_item_id: line.inventory_item_id,
            quantity: line.quantity,
          })),
        },
      }),
    onSuccess: (recipe) => {
      showSuccessToast(t("recipes.saved", { version: recipe.version }))
      onSaved(recipe)
      onOpenChange(false)
    },
    onError: (err: ApiError) => handleError.call(showErrorToast, err),
  })

  const addItem = (item: {
    id: string
    name: string
    sku: string
    base_unit: Unit
  }) => {
    const next: DraftLine = {
      inventory_item_id: item.id,
      item_name: item.name,
      item_sku: item.sku,
      base_unit: item.base_unit,
      quantity: "1",
    }
    setLines((current) =>
      productType === "direct_sale"
        ? [next]
        : current.some((line) => line.inventory_item_id === item.id)
          ? current
          : [...current, next],
    )
    setSearch("")
  }

  const submit = (event: FormEvent) => {
    event.preventDefault()
    save.mutate()
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{t("recipes.newVersion")}</DialogTitle>
        </DialogHeader>
        <form className="flex flex-col gap-4" onSubmit={submit}>
          <div className="flex flex-col gap-2">
            <Label htmlFor="effective-from">{t("recipes.effective")}</Label>
            <Input
              id="effective-from"
              type="datetime-local"
              value={effectiveFrom}
              onChange={(event) => setEffectiveFrom(event.target.value)}
              required
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="recipe-line-search">
              {t("recipes.lineSearch")}
            </Label>
            <Input
              id="recipe-line-search"
              data-testid="recipe-line-search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              autoComplete="off"
            />
            {matches.data && matches.data.data.length > 0 && (
              <div className="flex flex-col rounded-md border">
                {matches.data.data.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className="px-3 py-2 text-left text-sm hover:bg-muted"
                    onClick={() => addItem(item)}
                  >
                    {t("recipes.addLine", { name: item.name })}
                    <span className="ml-2 text-muted-foreground">
                      {item.sku} · {t(`unit.${item.base_unit}` as MessageKey)}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
          <div className="flex flex-col gap-2">
            {lines.map((line) => (
              <div
                key={line.inventory_item_id}
                className="grid grid-cols-[minmax(0,1fr)_7rem_6.5rem] items-center gap-2"
              >
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium">
                    {line.item_name}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {line.item_sku} ·{" "}
                    {t(`unit.${line.base_unit}` as MessageKey)}
                  </div>
                </div>
                <Input
                  aria-label={t("recipes.quantity")}
                  className="w-full"
                  inputMode="decimal"
                  value={line.quantity}
                  onChange={(event) =>
                    setLines((current) =>
                      current.map((row) =>
                        row.inventory_item_id === line.inventory_item_id
                          ? { ...row, quantity: event.target.value }
                          : row,
                      ),
                    )
                  }
                  required
                />
                <Button
                  type="button"
                  variant="outline"
                  className="w-full"
                  onClick={() =>
                    setLines((current) =>
                      current.filter(
                        (row) =>
                          row.inventory_item_id !== line.inventory_item_id,
                      ),
                    )
                  }
                >
                  {t("recipes.removeLine")}
                </Button>
              </div>
            ))}
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              {t("common.cancel")}
            </Button>
            <LoadingButton
              type="submit"
              data-testid="save-recipe"
              loading={save.isPending}
              disabled={lines.length === 0 || !effectiveFrom}
            >
              {t("common.save")}
            </LoadingButton>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
