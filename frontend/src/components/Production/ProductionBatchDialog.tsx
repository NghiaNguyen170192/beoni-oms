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
  type ProductionBatchTemplateCreate,
  RecipesService,
} from "@/client"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
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
  const [selectedTemplateId, setSelectedTemplateId] = useState("")
  const [templateName, setTemplateName] = useState("")
  const [templateToDelete, setTemplateToDelete] = useState<string>()
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
  const templates = useQuery({
    queryKey: ["productionBatchTemplates"],
    queryFn: () => ProductionApi.readBatchTemplates(),
    enabled: open && !batch,
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
    setSelectedTemplateId("")
    setTemplateName("")
    setTemplateToDelete(undefined)
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

  const saveTemplate = useMutation({
    mutationFn: () => {
      const body = {
        name: templateName.trim(),
        recipe_id: mode === "manual" ? null : formulaVersionId,
        formula_runs: mode === "manual" ? null : formulaRuns,
        ingredients:
          mode === "manual"
            ? ingredients.map((line) => ({
                inventory_item_id: line.inventory_item_id,
                planned_quantity: line.planned_quantity,
              }))
            : null,
        outputs: outputs.map((line) => ({
          menu_item_id: line.menu_item_id,
          inventory_item_id: line.inventory_item_id,
          planned_quantity: line.planned_quantity,
        })),
      } satisfies ProductionBatchTemplateCreate
      return ProductionApi.createBatchTemplate(body)
    },
    onSuccess: async () => {
      showSuccessToast(t("production.templates.saved"))
      setTemplateName("")
      await queryClient.invalidateQueries({
        queryKey: ["productionBatchTemplates"],
      })
    },
    onError: (error: ApiError) => handleError.call(showErrorToast, error),
  })

  const deleteTemplate = useMutation({
    mutationFn: (templateId: string) =>
      ProductionApi.deleteBatchTemplate(templateId),
    onSuccess: async () => {
      showSuccessToast(t("production.templates.deleted"))
      setSelectedTemplateId("")
      setTemplateToDelete(undefined)
      await queryClient.invalidateQueries({
        queryKey: ["productionBatchTemplates"],
      })
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

  const chooseTemplate = (value: string) => {
    if (value === "none") {
      setSelectedTemplateId("")
      return
    }
    const template = templateRows.find((row) => row.id === value)
    if (!template) return

    setSelectedTemplateId(template.id)
    setNotes("")
    setMode(template.recipe_id ? "formula" : "manual")
    setFormulaMenuItemId(template.recipe_menu_item_id ?? "")
    setFormulaVersionId(template.recipe_id ?? "")
    setFormulaRuns(quantityInput(template.formula_runs) || "1")
    setIngredients(
      template.ingredients.length
        ? template.ingredients.map((line) => ({
            inventory_item_id: line.inventory_item_id,
            planned_quantity: quantityInput(line.planned_quantity),
          }))
        : [{ ...EMPTY_INGREDIENT }],
    )
    setOutputs(
      template.outputs.map((line) => ({
        menu_item_id: line.menu_item_id,
        inventory_item_id: line.inventory_item_id,
        planned_quantity: quantityInput(line.planned_quantity),
      })),
    )
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
  const templateError =
    templates.error instanceof Error ? templates.error.message : null
  const templateRows = templates.data?.data ?? []
  const canSaveTemplate =
    Boolean(templateName.trim()) &&
    outputs.length > 0 &&
    outputs.every(
      (line) =>
        Boolean(line.menu_item_id) &&
        Boolean(line.inventory_item_id) &&
        Number(line.planned_quantity) > 0,
    ) &&
    (mode === "manual"
      ? ingredients.length > 0 &&
        ingredients.every(
          (line) =>
            Boolean(line.inventory_item_id) &&
            Number(line.planned_quantity) > 0,
        )
      : Boolean(formulaVersionId) &&
        Number(formulaRuns) > 0 &&
        !formulaVersions.isPending)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[calc(100dvh-2rem)] overflow-y-auto sm:max-w-3xl">
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
          {!batch && (
            <section className="grid gap-3 rounded-md border p-4">
              <div className="flex gap-2">
                <Select
                  value={selectedTemplateId || "none"}
                  onValueChange={chooseTemplate}
                  disabled={templates.isPending || templateRows.length === 0}
                >
                  <SelectTrigger className="w-full min-w-0">
                    <SelectValue
                      placeholder={t("production.templates.choose")}
                    />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">
                      {t("production.templates.choose")}
                    </SelectItem>
                    {templateRows.map((template) => (
                      <SelectItem key={template.id} value={template.id}>
                        {template.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {selectedTemplateId && (
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    aria-label={t("production.templates.delete")}
                    onClick={() => setTemplateToDelete(selectedTemplateId)}
                  >
                    <Trash2 />
                  </Button>
                )}
              </div>
              {templateRows.length === 0 && !templates.isPending && (
                <p className="text-sm text-muted-foreground">
                  {t("production.templates.empty")}
                </p>
              )}
              {templateError && (
                <p role="alert" className="text-sm text-destructive">
                  {templateError}
                </p>
              )}
              <div className="grid gap-2 sm:grid-cols-[1fr_auto]">
                <div className="flex flex-col gap-2">
                  <Label htmlFor="production-template-name">
                    {t("production.templates.name")}
                  </Label>
                  <Input
                    id="production-template-name"
                    value={templateName}
                    maxLength={120}
                    onChange={(event) => setTemplateName(event.target.value)}
                  />
                </div>
                <LoadingButton
                  type="button"
                  className="self-end"
                  loading={saveTemplate.isPending}
                  disabled={!canSaveTemplate}
                  onClick={() => saveTemplate.mutate()}
                >
                  {t("production.templates.saveAs")}
                </LoadingButton>
              </div>
            </section>
          )}
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
                <SelectTrigger id="production-plan-mode" className="w-full">
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
                  <SelectTrigger id="production-formula-menu" className="w-full">
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
                  <SelectTrigger id="production-formula-version" className="w-full">
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
      <ConfirmDialog
        open={Boolean(templateToDelete)}
        onOpenChange={(nextOpen) => !nextOpen && setTemplateToDelete(undefined)}
        title={t("production.templates.deleteTitle")}
        description={t("production.templates.deleteDescription")}
        confirmLabel={t("production.templates.delete")}
        destructive
        loading={deleteTemplate.isPending}
        onConfirm={() => {
          if (templateToDelete) deleteTemplate.mutate(templateToDelete)
        }}
      />
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
      <SelectTrigger className="w-full">
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
        <SelectTrigger className="w-full">
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
