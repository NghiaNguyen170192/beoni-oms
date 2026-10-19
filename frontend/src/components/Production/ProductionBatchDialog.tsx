import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Plus, Trash2 } from "lucide-react"
import { type FormEvent, useEffect, useState } from "react"
import type { ApiError } from "@/client"
import {
  CatalogService,
  type InventoryItemPublic,
  InventoryService,
  type MenuItemPublic,
  type ProductionBatchCreate,
  RecipesService,
} from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { LoadingButton } from "@/components/ui/loading-button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import useCustomToast from "@/hooks/useCustomToast"
import { useI18n } from "@/i18n"
import { UNIT_LABELS } from "@/lib/labels"
import { handleError } from "@/utils"
import type { ProductionBatch } from "./api"
import { ProductionApi } from "./api"

type IngredientDraft = {
  inventory_item_id: string
  planned_quantity: string
}

type OutputDraft = {
  menu_item_id: string
  inventory_item_id: string
  planned_quantity: string
}

const EMPTY_INGREDIENT: IngredientDraft = {
  inventory_item_id: "",
  planned_quantity: "1",
}
const EMPTY_OUTPUT: OutputDraft = {
  menu_item_id: "",
  inventory_item_id: "",
  planned_quantity: "1",
}

function localDateValue(): string {
  const now = new Date()
  const pad = (value: number) => String(value).padStart(2, "0")
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

function quantityInput(value: string | null | undefined): string {
  if (!value) return ""
  return value.replace(/(\.\d*?)0+$/, "$1").replace(/\.$/, "")
}

export function ProductionBatchDialog({
  open,
  onOpenChange,
  batch,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  batch?: ProductionBatch
}) {
  const { t } = useI18n()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const queryClient = useQueryClient()
  const [plannedFor, setPlannedFor] = useState(localDateValue)
  const [notes, setNotes] = useState("")
  const [mode, setMode] = useState<"manual" | "formula">("manual")
  const [formulaMenuItemId, setFormulaMenuItemId] = useState("")
  const [formulaVersionId, setFormulaVersionId] = useState("")
  const [formulaRuns, setFormulaRuns] = useState("1")
  const [ingredients, setIngredients] = useState<IngredientDraft[]>([
    { ...EMPTY_INGREDIENT },
  ])
  const [outputs, setOutputs] = useState<OutputDraft[]>([{ ...EMPTY_OUTPUT }])

  const inventory = useQuery({
    queryKey: ["inventoryItems", "production-form"],
    queryFn: () => InventoryService.readItems({ limit: 500 }),
    enabled: open,
  })
  const menu = useQuery({
    queryKey: ["catalogItems", "production-form"],
    queryFn: () => CatalogService.readItems({ isActive: true, limit: 500 }),
    enabled: open,
  })
  const formulaVersions = useQuery({
    queryKey: ["productionRecipeVersions", formulaMenuItemId],
    queryFn: () =>
      RecipesService.readRecipes({ menuItemId: formulaMenuItemId }),
    enabled: open && mode === "formula" && Boolean(formulaMenuItemId),
  })
  const batchFormula = useQuery({
    queryKey: ["productionRecipe", batch?.recipe_id],
    queryFn: () => RecipesService.readRecipe({ recipeId: batch!.recipe_id! }),
    enabled: open && Boolean(batch?.recipe_id),
  })

  const rawMaterials = (inventory.data?.data ?? []).filter(
    (item) => item.role === "raw_material",
  )
  const finishedGoods = (inventory.data?.data ?? []).filter(
    (item) => item.role === "finished_good",
  )
  const menuItems = (menu.data?.data ?? []).filter(
    (item) => item.product_type !== "non_stock",
  )
  const formulas = (formulaVersions.data?.data ?? []).filter(
    (recipe) => recipe.outputs.length > 0,
  )
  const selectedFormula = batch?.recipe_id
    ? batchFormula.data
    : formulas.find((recipe) => recipe.id === formulaVersionId)

  useEffect(() => {
    if (!open) return
    setPlannedFor(batch?.planned_for ?? localDateValue())
    setNotes(batch?.notes ?? "")
    setMode(batch?.recipe_id ? "formula" : "manual")
    setFormulaMenuItemId("")
    setFormulaVersionId(batch?.recipe_id ?? "")
    setFormulaRuns(batch?.formula_runs ?? "1")
    setIngredients(
      batch?.ingredients.length
        ? batch.ingredients.map((line) => ({
            inventory_item_id: line.inventory_item_id,
            planned_quantity: quantityInput(line.planned_quantity),
          }))
        : [{ ...EMPTY_INGREDIENT }],
    )
    setOutputs(
      batch?.outputs.length
        ? batch.outputs.map((line) => ({
            menu_item_id: line.menu_item_id,
            inventory_item_id: line.inventory_item_id,
            planned_quantity: quantityInput(line.planned_quantity),
          }))
        : [{ ...EMPTY_OUTPUT }],
    )
  }, [batch, open])

  const save = useMutation({
    mutationFn: () => {
      const ingredientLines = ingredients.map((line) => ({
        inventory_item_id: line.inventory_item_id,
        planned_quantity: line.planned_quantity,
      }))
      const outputLines = outputs.map((line) => ({
        menu_item_id: line.menu_item_id,
        inventory_item_id: line.inventory_item_id,
        planned_quantity: line.planned_quantity,
      }))
      return batch
        ? ProductionApi.updateBatch(batch.id, {
            planned_for: plannedFor,
            notes: notes.trim() || null,
            ...(mode === "manual"
              ? {
                  recipe_id: null,
                  formula_runs: null,
                  ingredients: ingredientLines,
                  outputs: outputLines,
                }
              : {
                  recipe_id: formulaVersionId,
                  formula_runs: formulaRuns,
                  outputs: outputLines,
                }),
          })
        : ProductionApi.createBatch({
            planned_for: plannedFor,
            notes: notes.trim() || null,
            recipe_id: mode === "manual" ? null : formulaVersionId,
            formula_runs: mode === "manual" ? null : formulaRuns,
            ingredients: mode === "manual" ? ingredientLines : null,
            outputs: outputLines,
          } satisfies ProductionBatchCreate)
    },
    onSuccess: async (saved) => {
      showSuccessToast(
        t(batch ? "production.batch.saved" : "production.batch.created", {
          number: saved.number,
        }),
      )
      await queryClient.invalidateQueries({ queryKey: ["productionBatches"] })
      await queryClient.invalidateQueries({
        queryKey: ["productionBatch", saved.id],
      })
      onOpenChange(false)
    },
    onError: (error: ApiError) => handleError.call(showErrorToast, error),
  })

  const updateIngredient = (
    index: number,
    field: keyof IngredientDraft,
    value: string,
  ) =>
    setIngredients((current) =>
      current.map((line, lineIndex) =>
        lineIndex === index ? { ...line, [field]: value } : line,
      ),
    )

  const updateOutput = (
    index: number,
    field: keyof OutputDraft,
    value: string,
  ) =>
    setOutputs((current) =>
      current.map((line, lineIndex) =>
        lineIndex === index ? { ...line, [field]: value } : line,
      ),
    )

  const submit = (event: FormEvent) => {
    event.preventDefault()
    save.mutate()
  }

  const catalogError =
    inventory.error instanceof Error
      ? inventory.error.message
      : menu.error instanceof Error
        ? menu.error.message
        : formulaVersions.error instanceof Error
          ? formulaVersions.error.message
          : batchFormula.error instanceof Error
            ? batchFormula.error.message
            : null

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>
            {t(
              batch
                ? "production.batch.editTitle"
                : "production.batch.createTitle",
              batch ? { number: batch.number } : undefined,
            )}
          </DialogTitle>
          <DialogDescription>
            {t("production.batch.formDescription")}
          </DialogDescription>
        </DialogHeader>
        <form className="flex flex-col gap-5" onSubmit={submit}>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="flex flex-col gap-2">
              <Label htmlFor="production-planned-for">
                {t("production.batch.plannedFor")}
              </Label>
              <Input
                id="production-planned-for"
                type="date"
                required
                value={plannedFor}
                onChange={(event) => setPlannedFor(event.target.value)}
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="production-notes">
                {t("production.batch.notes")}
              </Label>
              <Input
                id="production-notes"
                value={notes}
                maxLength={1000}
                onChange={(event) => setNotes(event.target.value)}
              />
            </div>
          </div>

          {!batch && (
            <div className="flex flex-col gap-2">
              <Label htmlFor="production-plan-mode">
                {t("production.batch.planType")}
              </Label>
              <Select
                value={mode}
                onValueChange={(value) =>
                  setMode(value as "manual" | "formula")
                }
              >
                <SelectTrigger id="production-plan-mode">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="manual">
                    {t("production.batch.manualPlan")}
                  </SelectItem>
                  <SelectItem value="formula">
                    {t("production.batch.formulaPlan")}
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}

          {mode === "formula" && !batch?.recipe_id && (
            <section className="grid gap-3 sm:grid-cols-2">
              <div className="flex flex-col gap-2">
                <Label htmlFor="production-formula-menu">
                  {t("production.batch.formulaMenuItem")}
                </Label>
                <Select
                  value={formulaMenuItemId}
                  onValueChange={(value) => {
                    setFormulaMenuItemId(value)
                    setFormulaVersionId("")
                    setOutputs([])
                  }}
                >
                  <SelectTrigger id="production-formula-menu">
                    <SelectValue
                      placeholder={t("production.batch.chooseMenuItem")}
                    />
                  </SelectTrigger>
                  <SelectContent>
                    {menuItems.map((item) => (
                      <SelectItem key={item.id} value={item.id}>
                        {item.code} · {item.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="production-formula-version">
                  {t("production.batch.formulaVersion")}
                </Label>
                <Select
                  value={formulaVersionId}
                  onValueChange={(value) => {
                    const recipe = formulas.find(
                      (candidate) => candidate.id === value,
                    )
                    setFormulaVersionId(value)
                    setOutputs(
                      recipe?.outputs.map((output) => ({
                        menu_item_id: output.menu_item_id,
                        inventory_item_id: output.inventory_item_id,
                        planned_quantity: quantityInput(output.quantity),
                      })) ?? [],
                    )
                  }}
                  disabled={!formulaMenuItemId || formulas.length === 0}
                >
                  <SelectTrigger id="production-formula-version">
                    <SelectValue
                      placeholder={t("production.batch.chooseFormula")}
                    />
                  </SelectTrigger>
                  <SelectContent>
                    {formulas.map((recipe) => (
                      <SelectItem key={recipe.id} value={recipe.id}>
                        {t("production.batch.formulaVersionLabel", {
                          version: recipe.version,
                        })}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {formulaMenuItemId &&
                  !formulaVersions.isPending &&
                  formulas.length === 0 && (
                    <p className="text-sm text-muted-foreground">
                      {t("production.batch.noFormula")}
                    </p>
                  )}
              </div>
            </section>
          )}

          {mode === "formula" && selectedFormula && (
            <section className="flex flex-col gap-3 rounded-md border p-4">
              <div className="grid gap-3 sm:grid-cols-[1fr_10rem] sm:items-end">
                <div>
                  <h3 className="font-semibold">
                    {selectedFormula.menu_item_name} ·{" "}
                    {t("production.batch.formulaVersionLabel", {
                      version: selectedFormula.version,
                    })}
                  </h3>
                  <p className="text-sm text-muted-foreground">
                    {t("production.batch.formulaScaleHint")}
                  </p>
                </div>
                <div className="flex flex-col gap-2">
                  <Label htmlFor="production-formula-runs">
                    {t("production.batch.formulaRuns")}
                  </Label>
                  <Input
                    id="production-formula-runs"
                    type="number"
                    min="0.0001"
                    step="0.0001"
                    required
                    value={formulaRuns}
                    onChange={(event) => setFormulaRuns(event.target.value)}
                  />
                </div>
              </div>
              <div className="text-sm">
                <div className="font-medium">
                  {t("production.batch.scaledIngredients")}
                </div>
                {selectedFormula.lines.map((line) => (
                  <div key={line.id} className="text-muted-foreground">
                    {line.item_name} ·{" "}
                    {quantityInput(
                      String(Number(line.quantity) * Number(formulaRuns)),
                    )}{" "}
                    {t(UNIT_LABELS[line.base_unit])}
                  </div>
                ))}
              </div>
              <div className="text-sm">
                <div className="font-medium">
                  {t("production.batch.selectFormulaOutputs")}
                </div>
                {outputs.map((line, index) => {
                  const formulaOutput = selectedFormula.outputs.find(
                    (output) =>
                      output.menu_item_id === line.menu_item_id &&
                      output.inventory_item_id === line.inventory_item_id,
                  )
                  return (
                    <div
                      key={`${line.menu_item_id}-${line.inventory_item_id}`}
                      className="mt-2 grid items-center gap-2 sm:grid-cols-[1fr_10rem_auto]"
                    >
                      <span>
                        {formulaOutput
                          ? `${formulaOutput.menu_item_name} · ${formulaOutput.item_name}`
                          : line.menu_item_id}
                      </span>
                      <Input
                        type="number"
                        min="0.0001"
                        step="0.0001"
                        required
                        aria-label={t("production.batch.plannedQuantity")}
                        value={line.planned_quantity}
                        onChange={(event) =>
                          updateOutput(
                            index,
                            "planned_quantity",
                            event.target.value,
                          )
                        }
                      />
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        aria-label={t("production.batch.removeLine")}
                        disabled={outputs.length <= 1}
                        onClick={() =>
                          setOutputs((current) =>
                            current.filter(
                              (_, lineIndex) => lineIndex !== index,
                            ),
                          )
                        }
                      >
                        <Trash2 />
                      </Button>
                    </div>
                  )
                })}
              </div>
            </section>
          )}

          {mode === "manual" && (
            <>
              <section className="flex flex-col gap-3">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold">
                    {t("production.batch.ingredients")}
                  </h3>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      setIngredients((current) => [
                        ...current,
                        { ...EMPTY_INGREDIENT },
                      ])
                    }
                  >
                    <Plus className="mr-1 size-4" />
                    {t("production.batch.addIngredient")}
                  </Button>
                </div>
                {ingredients.map((line, index) => (
                  <IngredientInput
                    key={`${index}-${line.inventory_item_id}`}
                    index={index}
                    line={line}
                    items={rawMaterials}
                    onChange={updateIngredient}
                    onRemove={() =>
                      setIngredients((current) =>
                        current.filter((_, lineIndex) => lineIndex !== index),
                      )
                    }
                    canRemove={ingredients.length > 1}
                  />
                ))}
              </section>

              <section className="flex flex-col gap-3">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold">
                    {t("production.batch.outputs")}
                  </h3>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      setOutputs((current) => [...current, { ...EMPTY_OUTPUT }])
                    }
                  >
                    <Plus className="mr-1 size-4" />
                    {t("production.batch.addOutput")}
                  </Button>
                </div>
                {outputs.map((line, index) => (
                  <OutputInput
                    key={`${index}-${line.menu_item_id}-${line.inventory_item_id}`}
                    index={index}
                    line={line}
                    menuItems={menuItems}
                    inventoryItems={finishedGoods}
                    onChange={updateOutput}
                    onRemove={() =>
                      setOutputs((current) =>
                        current.filter((_, lineIndex) => lineIndex !== index),
                      )
                    }
                    canRemove={outputs.length > 1}
                  />
                ))}
              </section>
            </>
          )}

          {catalogError && (
            <p role="alert" className="text-sm text-destructive">
              {catalogError}
            </p>
          )}
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
              loading={save.isPending}
              disabled={
                inventory.isPending ||
                menu.isPending ||
                (mode === "formula" && formulaVersions.isPending) ||
                (Boolean(batch?.recipe_id) && batchFormula.isPending) ||
                Boolean(catalogError) ||
                (mode === "manual" &&
                  (ingredients.length === 0 || outputs.length === 0)) ||
                (mode === "formula" &&
                  (!formulaVersionId || !formulaRuns || outputs.length === 0))
              }
            >
              {t("common.save")}
            </LoadingButton>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function InventorySelect({
  value,
  items,
  onChange,
  placeholder,
}: {
  value: string
  items: InventoryItemPublic[]
  onChange: (value: string) => void
  placeholder: string
}) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {items.map((item) => (
          <SelectItem key={item.id} value={item.id} disabled={!item.is_active}>
            {item.sku} · {item.name} · {item.base_unit}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

function IngredientInput({
  index,
  line,
  items,
  onChange,
  onRemove,
  canRemove,
}: {
  index: number
  line: IngredientDraft
  items: InventoryItemPublic[]
  onChange: (index: number, field: keyof IngredientDraft, value: string) => void
  onRemove: () => void
  canRemove: boolean
}) {
  const { t } = useI18n()
  return (
    <div className="grid gap-2 sm:grid-cols-[1fr_10rem_auto]">
      <InventorySelect
        value={line.inventory_item_id}
        items={items}
        placeholder={t("production.batch.chooseIngredient")}
        onChange={(value) => onChange(index, "inventory_item_id", value)}
      />
      <Input
        type="number"
        min="0.0001"
        step="0.0001"
        required
        aria-label={t("production.batch.plannedQuantity")}
        value={line.planned_quantity}
        onChange={(event) =>
          onChange(index, "planned_quantity", event.target.value)
        }
      />
      <Button
        type="button"
        variant="ghost"
        size="icon"
        aria-label={t("production.batch.removeLine")}
        disabled={!canRemove}
        onClick={onRemove}
      >
        <Trash2 />
      </Button>
    </div>
  )
}

function OutputInput({
  index,
  line,
  menuItems,
  inventoryItems,
  onChange,
  onRemove,
  canRemove,
}: {
  index: number
  line: OutputDraft
  menuItems: MenuItemPublic[]
  inventoryItems: InventoryItemPublic[]
  onChange: (index: number, field: keyof OutputDraft, value: string) => void
  onRemove: () => void
  canRemove: boolean
}) {
  const { t } = useI18n()
  return (
    <div className="grid gap-2 sm:grid-cols-[1fr_1fr_10rem_auto]">
      <Select
        value={line.menu_item_id}
        onValueChange={(value) => onChange(index, "menu_item_id", value)}
      >
        <SelectTrigger>
          <SelectValue placeholder={t("production.batch.chooseMenuItem")} />
        </SelectTrigger>
        <SelectContent>
          {menuItems.map((item) => (
            <SelectItem key={item.id} value={item.id}>
              {item.code} · {item.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <div className="flex flex-col gap-1">
        <InventorySelect
          value={line.inventory_item_id}
          items={inventoryItems}
          placeholder={t("production.batch.chooseFinishedGood")}
          onChange={(value) => onChange(index, "inventory_item_id", value)}
        />
        {inventoryItems.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            {t("production.batch.noFinishedGoods")}
          </p>
        ) : null}
      </div>
      <Input
        type="number"
        min="0.0001"
        step="0.0001"
        required
        aria-label={t("production.batch.plannedQuantity")}
        value={line.planned_quantity}
        onChange={(event) =>
          onChange(index, "planned_quantity", event.target.value)
        }
      />
      <Button
        type="button"
        variant="ghost"
        size="icon"
        aria-label={t("production.batch.removeLine")}
        disabled={!canRemove}
        onClick={onRemove}
      >
        <Trash2 />
      </Button>
    </div>
  )
}
