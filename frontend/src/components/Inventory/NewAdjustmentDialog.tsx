import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Plus, Trash2 } from "lucide-react"
import { useState } from "react"

import {
  type AdjustmentReason,
  type ApiError,
  InventoryService,
  type StockAdjustmentLineCreate,
} from "@/client"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import useCustomToast from "@/hooks/useCustomToast"
import { type MessageKey, useI18n } from "@/i18n"
import { formatNumber } from "@/lib/format"
import { useIdempotencyKey } from "@/lib/idempotency"
import {
  ADJUSTMENT_REASON_LABELS,
  ADJUSTMENT_REASONS,
  DECREASE_REASONS,
  UNIT_LABELS,
} from "@/lib/labels"
import { handleError } from "@/utils"
import { inventoryItemsQueryOptions } from "./queries"

const QUANTITY = /^-?\d+(\.\d{1,4})?$/

type Line = {
  key: number
  itemId: string
  reason: AdjustmentReason
  /** Counted quantity, quantity removed (decrease reasons), or signed change. */
  amount: string
  unitCost: string
}

let nextLineKey = 0
const emptyLine = (reason: AdjustmentReason = "spoilage"): Line => ({
  key: nextLineKey++,
  itemId: "",
  reason,
  amount: "",
  unitCost: "",
})

function amountLabel(reason: AdjustmentReason): MessageKey {
  if (reason === "physical_count")
    return "inventory.newAdjustment.countedQuantity"
  if (DECREASE_REASONS.includes(reason))
    return "inventory.newAdjustment.quantityRemoved"
  return "inventory.newAdjustment.change"
}

function lineError(line: Line): MessageKey | null {
  if (!line.itemId) return "inventory.newAdjustment.chooseItem"
  const amount = line.amount.trim()
  if (!QUANTITY.test(amount)) return "inventory.newAdjustment.invalidQuantity"
  const value = Number(amount)
  if (line.reason === "physical_count") {
    if (value < 0) return "inventory.newAdjustment.countedNegative"
  } else if (DECREASE_REASONS.includes(line.reason)) {
    if (value <= 0) return "inventory.newAdjustment.removedNotPositive"
  } else if (value === 0) {
    return "inventory.newAdjustment.changeZero"
  }
  const cost = line.unitCost.trim()
  if (cost && !/^\d+(\.\d{1,4})?$/.test(cost))
    return "inventory.newAdjustment.invalidUnitCost"
  return null
}

function toPayload(line: Line): StockAdjustmentLineCreate {
  const amount = line.amount.trim()
  const unitCost = line.unitCost.trim() || null
  if (line.reason === "physical_count") {
    return {
      item_id: line.itemId,
      reason: line.reason,
      counted_quantity: amount,
      unit_cost: unitCost,
    }
  }
  if (DECREASE_REASONS.includes(line.reason)) {
    return {
      item_id: line.itemId,
      reason: line.reason,
      quantity_change: `-${amount.replace(/^-/, "")}`,
    }
  }
  return {
    item_id: line.itemId,
    reason: line.reason,
    quantity_change: amount,
    unit_cost: amount.startsWith("-") ? null : unitCost,
  }
}

const allowsUnitCost = (line: Line) =>
  line.reason === "physical_count" ||
  (line.reason === "correction" && !line.amount.trim().startsWith("-"))

export function NewAdjustmentDialog() {
  const { t } = useI18n()
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const idempotencyKey = useIdempotencyKey()
  const [open, setOpen] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [note, setNote] = useState("")
  const [lines, setLines] = useState<Line[]>([emptyLine()])
  const [showErrors, setShowErrors] = useState(false)

  const { data: itemData } = useQuery({
    ...inventoryItemsQueryOptions({ isActive: true }),
    enabled: open,
  })
  const items = itemData?.data ?? []
  const itemsById = new Map(items.map((item) => [item.id, item]))

  const edit = (updater: (current: Line[]) => Line[]) => {
    idempotencyKey.reset()
    setLines(updater)
  }
  const updateLine = (key: number, patch: Partial<Line>) =>
    edit((current) =>
      current.map((line) => (line.key === key ? { ...line, ...patch } : line)),
    )

  const reset = () => {
    idempotencyKey.reset()
    setNote("")
    setLines([emptyLine()])
    setShowErrors(false)
  }

  const post = useMutation({
    mutationFn: () =>
      InventoryService.postAdjustment({
        idempotencyKey: idempotencyKey.current(),
        requestBody: { note: note.trim() || null, lines: lines.map(toPayload) },
      }),
    onSuccess: (adjustment) => {
      showSuccessToast(
        t("inventory.newAdjustment.postedToast", {
          number: adjustment.number,
        }),
      )
      setConfirming(false)
      setOpen(false)
      reset()
    },
    onError: (err: ApiError) => {
      setConfirming(false)
      handleError.call(showErrorToast, err)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["stockAdjustments"] })
      queryClient.invalidateQueries({ queryKey: ["inventoryItems"] })
      queryClient.invalidateQueries({ queryKey: ["inventoryMovements"] })
    },
  })

  const chosen = lines.map((line) => line.itemId).filter(Boolean)
  const duplicate = chosen.length !== new Set(chosen).size
  const hasErrors = duplicate || lines.some((line) => lineError(line) !== null)

  const review = () => {
    setShowErrors(true)
    if (!hasErrors) setConfirming(true)
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (!next) reset()
      }}
    >
      <DialogTrigger asChild>
        <Button>
          <Plus className="mr-2" />
          {t("inventory.newAdjustment.button")}
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>{t("inventory.newAdjustment.title")}</DialogTitle>
          <DialogDescription>
            {t("inventory.newAdjustment.description")}
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-3 py-2">
          {lines.map((line, index) => {
            const item = itemsById.get(line.itemId)
            const error = showErrors ? lineError(line) : null
            return (
              <div
                key={line.key}
                className="grid gap-2 rounded-md border p-3 sm:grid-cols-[2fr_1.4fr_1fr_1fr_auto] sm:items-end"
                data-testid={`adjustment-line-${index}`}
              >
                <div className="grid gap-1.5">
                  <Label>{t("inventory.adjustments.item")}</Label>
                  <Select
                    value={line.itemId}
                    onValueChange={(itemId) => updateLine(line.key, { itemId })}
                  >
                    <SelectTrigger
                      className="w-full"
                      aria-label={t("inventory.newAdjustment.itemForLine", {
                        line: index + 1,
                      })}
                    >
                      <SelectValue
                        placeholder={t("inventory.newAdjustment.chooseItem")}
                      />
                    </SelectTrigger>
                    <SelectContent>
                      {items.map((option) => (
                        <SelectItem key={option.id} value={option.id}>
                          {option.sku} · {option.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {item && (
                    <span className="text-xs text-muted-foreground">
                      {t("inventory.newAdjustment.onHand", {
                        quantity: formatNumber(item.quantity),
                        unit: t(UNIT_LABELS[item.base_unit]),
                      })}
                    </span>
                  )}
                </div>
                <div className="grid gap-1.5">
                  <Label>{t("inventory.adjustments.reason")}</Label>
                  <Select
                    value={line.reason}
                    onValueChange={(reason) =>
                      updateLine(line.key, {
                        reason: reason as AdjustmentReason,
                        unitCost: "",
                      })
                    }
                  >
                    <SelectTrigger
                      className="w-full"
                      aria-label={t("inventory.newAdjustment.reasonForLine", {
                        line: index + 1,
                      })}
                    >
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {ADJUSTMENT_REASONS.map((reason) => (
                        <SelectItem key={reason} value={reason}>
                          {t(ADJUSTMENT_REASON_LABELS[reason])}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor={`adjustment-amount-${line.key}`}>
                    {t(amountLabel(line.reason))}
                  </Label>
                  <Input
                    id={`adjustment-amount-${line.key}`}
                    inputMode="decimal"
                    value={line.amount}
                    onChange={(e) =>
                      updateLine(line.key, { amount: e.target.value })
                    }
                  />
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor={`adjustment-cost-${line.key}`}>
                    {t("inventory.newAdjustment.unitCost")}
                  </Label>
                  <Input
                    id={`adjustment-cost-${line.key}`}
                    inputMode="decimal"
                    placeholder={
                      allowsUnitCost(line)
                        ? t("inventory.newAdjustment.averageCost")
                        : "—"
                    }
                    disabled={!allowsUnitCost(line)}
                    value={line.unitCost}
                    onChange={(e) =>
                      updateLine(line.key, { unitCost: e.target.value })
                    }
                  />
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={t("inventory.newAdjustment.removeLine", {
                    line: index + 1,
                  })}
                  disabled={lines.length === 1}
                  onClick={() =>
                    edit((current) => current.filter((l) => l.key !== line.key))
                  }
                >
                  <Trash2 />
                </Button>
                {error && (
                  <p className="text-sm text-destructive sm:col-span-5">
                    {t(error)}
                  </p>
                )}
              </div>
            )
          })}
          {showErrors && duplicate && (
            <p className="text-sm text-destructive">
              {t("inventory.newAdjustment.duplicateItem")}
            </p>
          )}
          <Button
            variant="outline"
            className="w-fit"
            onClick={() =>
              edit((current) => [
                ...current,
                emptyLine(current[current.length - 1]?.reason),
              ])
            }
          >
            <Plus className="mr-2" />
            {t("inventory.newAdjustment.addLine")}
          </Button>
          <div className="grid gap-1.5">
            <Label htmlFor="adjustment-note">{t("common.note")}</Label>
            <Input
              id="adjustment-note"
              maxLength={500}
              value={note}
              onChange={(e) => {
                idempotencyKey.reset()
                setNote(e.target.value)
              }}
            />
          </div>
        </div>

        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline">{t("common.cancel")}</Button>
          </DialogClose>
          <Button onClick={review}>
            {t("inventory.newAdjustment.review")}
          </Button>
        </DialogFooter>

        <ConfirmDialog
          open={confirming}
          onOpenChange={setConfirming}
          title={t("inventory.newAdjustment.confirmTitle")}
          description={t("inventory.newAdjustment.confirmDescription")}
          confirmLabel={t("inventory.newAdjustment.post")}
          loading={post.isPending}
          onConfirm={() => post.mutate()}
        >
          <ul className="text-sm list-disc pl-5">
            {lines.map((line) => {
              const item = itemsById.get(line.itemId)
              return (
                <li key={line.key}>
                  {item?.name ?? "?"}:{" "}
                  {t(ADJUSTMENT_REASON_LABELS[line.reason])}{" "}
                  {t(amountLabel(line.reason)).toLowerCase()} {line.amount}{" "}
                  {item && t(UNIT_LABELS[item.base_unit])}
                </li>
              )
            })}
          </ul>
        </ConfirmDialog>
      </DialogContent>
    </Dialog>
  )
}
