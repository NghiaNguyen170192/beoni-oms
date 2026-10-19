import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect, useState } from "react"

import type { ApiError } from "@/client"
import { editableQuantity } from "@/components/Inventory/queries"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { LoadingButton } from "@/components/ui/loading-button"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import useAuth from "@/hooks/useAuth"
import { useFormatters } from "@/hooks/useBusinessSettings"
import useCustomToast from "@/hooks/useCustomToast"
import { useI18n } from "@/i18n"
import { formatNumber } from "@/lib/format"
import { UNIT_LABELS } from "@/lib/labels"
import { hasPermission } from "@/lib/permissions"
import badgeStyles from "@/styles/badge.module.css"
import { handleError } from "@/utils"
import { ProductionApi, type ProductionBatch } from "./api"
import {
  productionBatchQueryOptions,
  productionTraceabilityQueryOptions,
} from "./queries"

function localDateTimeValue(): string {
  const now = new Date()
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000)
  return local.toISOString().slice(0, 16)
}

function localDateTimeToIso(value: string): string {
  return new Date(value).toISOString()
}

export function ProductionBatchDetail({
  batchId,
  onClose,
  onEdit,
}: {
  batchId: string | undefined
  onClose: () => void
  onEdit: (batch: ProductionBatch) => void
}) {
  const { t } = useI18n()
  const { user } = useAuth()
  const { formatDateTime, formatMoney } = useFormatters()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const queryClient = useQueryClient()
  const [completing, setCompleting] = useState(false)
  const [reversing, setReversing] = useState(false)
  const [finishedAt, setFinishedAt] = useState(localDateTimeValue)
  const [ingredientActuals, setIngredientActuals] = useState<
    Record<string, string>
  >({})
  const [outputActuals, setOutputActuals] = useState<
    Record<string, { good: string; waste: string }>
  >({})
  const [reversalReason, setReversalReason] = useState("")

  const batchQuery = useQuery({
    ...productionBatchQueryOptions(batchId ?? ""),
    enabled: batchId !== undefined,
  })
  const batch = batchQuery.data
  const canTrace = hasPermission(user, "production:traceability")
  const traceability = useQuery({
    ...productionTraceabilityQueryOptions(batchId ?? ""),
    enabled: batchId !== undefined && batch?.status === "completed" && canTrace,
  })

  useEffect(() => {
    if (batch?.status !== "draft") return
    setFinishedAt(localDateTimeValue())
    setIngredientActuals(
      Object.fromEntries(
        batch.ingredients.map((line) => [
          line.id,
          editableQuantity(line.actual_quantity ?? line.planned_quantity),
        ]),
      ),
    )
    setOutputActuals(
      Object.fromEntries(
        batch.outputs.map((line) => [
          line.id,
          {
            good: editableQuantity(
              line.actual_good_quantity ?? line.planned_quantity,
            ),
            waste: editableQuantity(line.waste_quantity),
          },
        ]),
      ),
    )
  }, [batch])

  const invalidateBatch = async () => {
    await queryClient.invalidateQueries({ queryKey: ["productionBatches"] })
    if (batchId) {
      await queryClient.invalidateQueries({
        queryKey: ["productionBatch", batchId],
      })
      await queryClient.invalidateQueries({
        queryKey: ["productionTraceability", batchId],
      })
    }
  }

  const complete = useMutation({
    mutationFn: () => {
      if (!batch) throw new Error("Batch details are unavailable")
      return ProductionApi.completeBatch(batch.id, crypto.randomUUID(), {
        finished_at: localDateTimeToIso(finishedAt),
        ingredients: batch.ingredients.map((line) => ({
          line_id: line.id,
          actual_quantity: ingredientActuals[line.id] ?? "0",
        })),
        outputs: batch.outputs.map((line) => ({
          line_id: line.id,
          actual_good_quantity: outputActuals[line.id]?.good ?? "0",
          waste_quantity: outputActuals[line.id]?.waste ?? "0",
        })),
      })
    },
    onSuccess: async (saved) => {
      showSuccessToast(
        t("production.batch.completed", { number: saved.number }),
      )
      setCompleting(false)
      await invalidateBatch()
      await queryClient.invalidateQueries({
        queryKey: ["productionAvailability"],
      })
    },
    onError: (error: ApiError) => handleError.call(showErrorToast, error),
  })

  const reverse = useMutation({
    mutationFn: () => {
      if (!batch) throw new Error("Batch details are unavailable")
      return ProductionApi.reverseBatch(
        batch.id,
        crypto.randomUUID(),
        reversalReason,
      )
    },
    onSuccess: async (saved) => {
      showSuccessToast(t("production.batch.reversed", { number: saved.number }))
      setReversing(false)
      setReversalReason("")
      await invalidateBatch()
      await queryClient.invalidateQueries({
        queryKey: ["productionAvailability"],
      })
    },
    onError: (error: ApiError) => handleError.call(showErrorToast, error),
  })

  const canManage = hasPermission(user, "production:manage")
  const canComplete = hasPermission(user, "production:complete")
  const canReverse = hasPermission(user, "production:reverse")

  return (
    <Sheet
      open={batchId !== undefined}
      onOpenChange={(open) => {
        if (!open) onClose()
      }}
    >
      <SheetContent className="w-full overflow-y-auto sm:max-w-3xl">
        {batchId && (
          <div className="flex flex-col gap-5 p-4">
            {batchQuery.isPending ? (
              <Skeleton className="h-32" />
            ) : batchQuery.error ? (
              <p role="alert" className="text-sm text-destructive">
                {batchQuery.error.message}
              </p>
            ) : batch ? (
              <>
                <SheetHeader className="p-0">
                  <SheetTitle>
                    {t("production.batch.number", { number: batch.number })}
                  </SheetTitle>
                  <SheetDescription>
                    <Badge
                      className={
                        batch.status === "completed"
                          ? badgeStyles.green
                          : batch.status === "draft"
                            ? badgeStyles.blue
                            : badgeStyles.red
                      }
                    >
                      {t(`production.status.${batch.status}`)}
                    </Badge>{" "}
                    · {t("production.batch.plannedFor")}: {batch.planned_for}
                    {batch.finished_at
                      ? ` · ${t("production.batch.finishedAt")}: ${formatDateTime(batch.finished_at)}`
                      : ""}
                  </SheetDescription>
                </SheetHeader>
                <div className="flex flex-wrap gap-2">
                  {canManage && batch.status === "draft" && (
                    <Button variant="outline" onClick={() => onEdit(batch)}>
                      {t("common.edit")}
                    </Button>
                  )}
                  {canComplete && batch.status === "draft" && (
                    <Button
                      onClick={() => {
                        setCompleting((current) => !current)
                        setReversing(false)
                      }}
                    >
                      {t("production.batch.completeAction")}
                    </Button>
                  )}
                  {canReverse && batch.status === "completed" && (
                    <Button
                      variant="destructive"
                      onClick={() => {
                        setReversing((current) => !current)
                        setCompleting(false)
                      }}
                    >
                      {t("production.batch.reverseAction")}
                    </Button>
                  )}
                </div>

                {completing && (
                  <section className="flex flex-col gap-3 rounded-md border p-4">
                    <h3 className="font-semibold">
                      {t("production.batch.actuals")}
                    </h3>
                    <div className="flex flex-col gap-2">
                      <Label htmlFor="batch-finished-at">
                        {t("production.batch.finishedAt")}
                      </Label>
                      <Input
                        id="batch-finished-at"
                        type="datetime-local"
                        required
                        value={finishedAt}
                        onChange={(event) => setFinishedAt(event.target.value)}
                      />
                    </div>
                    <div className="flex flex-col gap-2">
                      <h4 className="font-medium">
                        {t("production.batch.ingredients")}
                      </h4>
                      {batch.ingredients.map((line) => (
                        <div
                          key={line.id}
                          className="grid items-center gap-2 sm:grid-cols-[1fr_10rem]"
                        >
                          <Label htmlFor={`ingredient-${line.id}`}>
                            {line.item_name} · {t(UNIT_LABELS[line.unit])}
                            <span className="block text-xs text-muted-foreground">
                              {t("production.batch.planned")}:{" "}
                              {formatNumber(line.planned_quantity)}
                            </span>
                          </Label>
                          <Input
                            id={`ingredient-${line.id}`}
                            type="number"
                            min="0"
                            step="0.0001"
                            required
                            value={ingredientActuals[line.id] ?? ""}
                            onChange={(event) =>
                              setIngredientActuals((current) => ({
                                ...current,
                                [line.id]: event.target.value,
                              }))
                            }
                          />
                        </div>
                      ))}
                    </div>
                    <div className="flex flex-col gap-2">
                      <h4 className="font-medium">
                        {t("production.batch.outputs")}
                      </h4>
                      {batch.outputs.map((line) => (
                        <div
                          key={line.id}
                          className="flex flex-col gap-2 rounded-md bg-muted/40 p-3"
                        >
                          <div className="font-medium">
                            {line.menu_item_name}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {t("production.batch.planned")}:{" "}
                            {formatNumber(line.planned_quantity)}{" "}
                            {t(UNIT_LABELS[line.unit])}
                          </div>
                          <div className="grid gap-2 sm:grid-cols-2">
                            <div className="flex flex-col gap-1">
                              <Label htmlFor={`good-${line.id}`}>
                                {t("production.batch.actualGood")}
                              </Label>
                              <Input
                                id={`good-${line.id}`}
                                type="number"
                                min="0"
                                step="0.0001"
                                required
                                value={outputActuals[line.id]?.good ?? ""}
                                onChange={(event) =>
                                  setOutputActuals((current) => ({
                                    ...current,
                                    [line.id]: {
                                      good: event.target.value,
                                      waste: current[line.id]?.waste ?? "0",
                                    },
                                  }))
                                }
                              />
                            </div>
                            <div className="flex flex-col gap-1">
                              <Label htmlFor={`waste-${line.id}`}>
                                {t("production.batch.waste")}
                              </Label>
                              <Input
                                id={`waste-${line.id}`}
                                type="number"
                                min="0"
                                step="0.0001"
                                required
                                value={outputActuals[line.id]?.waste ?? ""}
                                onChange={(event) =>
                                  setOutputActuals((current) => ({
                                    ...current,
                                    [line.id]: {
                                      good: current[line.id]?.good ?? "0",
                                      waste: event.target.value,
                                    },
                                  }))
                                }
                              />
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                    <div className="flex gap-2">
                      <LoadingButton
                        loading={complete.isPending}
                        onClick={() => complete.mutate()}
                        disabled={!finishedAt}
                      >
                        {t("production.batch.completeAction")}
                      </LoadingButton>
                      <Button
                        variant="outline"
                        onClick={() => setCompleting(false)}
                      >
                        {t("common.cancel")}
                      </Button>
                    </div>
                  </section>
                )}

                {reversing && (
                  <section className="flex flex-col gap-3 rounded-md border border-destructive/40 p-4">
                    <Label htmlFor="batch-reversal-reason">
                      {t("production.batch.reversalReason")}
                    </Label>
                    <Input
                      id="batch-reversal-reason"
                      required
                      maxLength={255}
                      value={reversalReason}
                      onChange={(event) =>
                        setReversalReason(event.target.value)
                      }
                    />
                    <div className="flex gap-2">
                      <LoadingButton
                        variant="destructive"
                        loading={reverse.isPending}
                        onClick={() => reverse.mutate()}
                        disabled={!reversalReason.trim()}
                      >
                        {t("production.batch.reverseAction")}
                      </LoadingButton>
                      <Button
                        variant="outline"
                        onClick={() => setReversing(false)}
                      >
                        {t("common.cancel")}
                      </Button>
                    </div>
                  </section>
                )}

                <section className="flex flex-col gap-2">
                  <h3 className="font-semibold">
                    {t("production.batch.ingredients")}
                  </h3>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t("inventory.field.name")}</TableHead>
                        <TableHead className="text-right">
                          {t("production.batch.planned")}
                        </TableHead>
                        <TableHead className="text-right">
                          {t("production.batch.actual")}
                        </TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {batch.ingredients.map((line) => (
                        <TableRow key={line.id}>
                          <TableCell>
                            {line.item_name} · {t(UNIT_LABELS[line.unit])}
                          </TableCell>
                          <TableCell className="text-right tabular-nums">
                            {formatNumber(line.planned_quantity)}
                          </TableCell>
                          <TableCell className="text-right tabular-nums">
                            {line.actual_quantity === null
                              ? "—"
                              : formatNumber(line.actual_quantity)}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </section>

                <section className="flex flex-col gap-2">
                  <h3 className="font-semibold">
                    {t("production.batch.outputs")}
                  </h3>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>
                          {t("production.batch.outputProduct")}
                        </TableHead>
                        <TableHead className="text-right">
                          {t("production.batch.planned")}
                        </TableHead>
                        <TableHead className="text-right">
                          {t("production.batch.actualGood")}
                        </TableHead>
                        <TableHead className="text-right">
                          {t("production.batch.waste")}
                        </TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {batch.outputs.map((line) => (
                        <TableRow key={line.id}>
                          <TableCell>
                            {line.menu_item_name} · {t(UNIT_LABELS[line.unit])}
                          </TableCell>
                          <TableCell className="text-right tabular-nums">
                            {formatNumber(line.planned_quantity)}
                          </TableCell>
                          <TableCell className="text-right tabular-nums">
                            {line.actual_good_quantity === null
                              ? "—"
                              : formatNumber(line.actual_good_quantity)}
                          </TableCell>
                          <TableCell className="text-right tabular-nums">
                            {formatNumber(line.waste_quantity)}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </section>

                {batch.status === "completed" && (
                  <div className="rounded-md bg-muted p-3">
                    <div className="text-sm text-muted-foreground">
                      {t("production.batch.materialCost")}
                    </div>
                    <div className="font-semibold">
                      {batch.total_material_cost === null
                        ? t("production.batch.costUnknown")
                        : formatMoney(batch.total_material_cost)}
                    </div>
                  </div>
                )}

                {canTrace && batch.status === "completed" && (
                  <section className="flex flex-col gap-3">
                    <h3 className="font-semibold">
                      {t("production.batch.traceability")}
                    </h3>
                    {traceability.isPending ? (
                      <Skeleton className="h-24" />
                    ) : traceability.error ? (
                      <p role="alert" className="text-sm text-destructive">
                        {traceability.error.message}
                      </p>
                    ) : (
                      (traceability.data?.lots ?? []).map((lot) => (
                        <div key={lot.lot_id} className="rounded-md border p-3">
                          <div className="font-medium">
                            {lot.lot_number} · {lot.item_name}
                          </div>
                          <div className="text-sm text-muted-foreground">
                            {t("production.batch.produced")}:{" "}
                            {formatNumber(lot.produced_quantity)} ·{" "}
                            {t("production.batch.onHand")}:{" "}
                            {formatNumber(lot.quantity_on_hand)} ·{" "}
                            {t("production.batch.available")}:{" "}
                            {formatNumber(lot.available_quantity)}
                          </div>
                          <div className="mt-2 flex flex-col gap-2">
                            {lot.orders.map((order) => (
                              <div
                                key={`${lot.lot_id}-${order.order_line_id}`}
                                className="border-l-2 pl-3 text-sm"
                              >
                                <div>
                                  {t("production.batch.orderNumber", {
                                    number: order.order_number,
                                  })}{" "}
                                  · {order.item_name} ·{" "}
                                  {formatNumber(order.allocated_quantity)}
                                </div>
                                {order.returns.map((returned) => (
                                  <div
                                    key={returned.stock_return_line_id}
                                    className="text-muted-foreground"
                                  >
                                    {t("production.batch.returnQuantity", {
                                      quantity: formatNumber(returned.quantity),
                                    })}{" "}
                                    ·{" "}
                                    {returned.sellable
                                      ? t("production.batch.sellable")
                                      : t("production.batch.unsellable")}
                                  </div>
                                ))}
                              </div>
                            ))}
                          </div>
                        </div>
                      ))
                    )}
                  </section>
                )}
              </>
            ) : null}
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}
