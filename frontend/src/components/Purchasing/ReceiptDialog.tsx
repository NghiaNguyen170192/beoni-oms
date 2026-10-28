import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Plus, Trash2 } from "lucide-react"
import { useEffect, useState } from "react"

import { PurchasingService, type StockReceiptPublic } from "@/client"
import { inventoryItemsQueryOptions } from "@/components/Inventory/queries"
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
import { SearchableSelect } from "@/components/ui/searchable-select"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useFormatters } from "@/hooks/useBusinessSettings"
import useCustomToast from "@/hooks/useCustomToast"
import { useI18n } from "@/i18n"
import { formatAmountInput, parseAmountInput } from "@/lib/format"
import { UNIT_LABELS } from "@/lib/labels"
import { handleError } from "@/utils"

type Line = {
  key: number
  itemId: string
  quantity: string
  cost: string
}

let nextKey = 1
const emptyLine = (): Line => ({
  key: nextKey++,
  itemId: "",
  quantity: "",
  cost: "",
})

function preview(line: Line): number | null {
  const quantity = Number(line.quantity)
  const cost = Number(line.cost)
  if (
    !line.quantity ||
    !line.cost ||
    Number.isNaN(quantity) ||
    Number.isNaN(cost)
  ) {
    return null
  }
  return quantity * cost
}

export function ReceiptDialog({
  open,
  onOpenChange,
  receipt,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  receipt?: StockReceiptPublic
}) {
  const { t } = useI18n()
  const { formatMoney } = useFormatters()
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [supplierId, setSupplierId] = useState("")
  const [receiptDate, setReceiptDate] = useState(
    new Date().toISOString().slice(0, 10),
  )
  const [notes, setNotes] = useState("")
  const [lines, setLines] = useState<Line[]>([emptyLine()])

  useEffect(() => {
    if (!open) return

    setSupplierId(receipt?.supplier_id ?? "")
    setReceiptDate(
      receipt?.receipt_date ?? new Date().toISOString().slice(0, 10),
    )
    setNotes(receipt?.notes ?? "")
    setLines(
      receipt
        ? receipt.lines.map((line) => ({
            key: nextKey++,
            itemId: line.item_id,
            quantity: line.purchase_qty,
            cost: line.purchase_unit_cost,
          }))
        : [emptyLine()],
    )
  }, [open, receipt])

  const { data: suppliers } = useQuery({
    queryKey: ["suppliers", "active"],
    queryFn: () =>
      PurchasingService.readSuppliers({ isActive: true, limit: 500 }),
    enabled: open,
  })
  const { data: items } = useQuery({
    ...inventoryItemsQueryOptions({ isActive: true }),
    enabled: open,
  })
  const itemRows = items?.data ?? []

  const save = useMutation({
    mutationFn: () => {
      const body = {
        supplier_id: supplierId,
        receipt_date: receiptDate,
        notes: notes.trim() || null,
        lines: lines.map((line) => ({
          item_id: line.itemId,
          purchase_quantity: line.quantity,
          purchase_unit_cost: line.cost,
        })),
      }
      return receipt
        ? PurchasingService.updateReceipt({
            receiptId: receipt.id,
            requestBody: body,
          })
        : PurchasingService.createReceipt({ requestBody: body })
    },
    onSuccess: () => {
      showSuccessToast(t("purchasing.receipts.saved"))
      onOpenChange(false)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["receipts"] }),
  })

  const valid =
    supplierId &&
    receiptDate &&
    lines.every(
      (line) => line.itemId && Number(line.quantity) > 0 && line.cost !== "",
    )

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {receipt
              ? t("purchasing.receipts.edit")
              : t("purchasing.receipts.add")}
          </DialogTitle>
        </DialogHeader>
        <div className="grid gap-3">
          <div className="grid gap-1.5">
            <Label>{t("purchasing.receipts.field.supplier")}</Label>
            <Select value={supplierId} onValueChange={setSupplierId}>
              <SelectTrigger
                aria-label={t("purchasing.receipts.field.supplier")}
              >
                <SelectValue
                  placeholder={t("purchasing.receipts.chooseSupplier")}
                />
              </SelectTrigger>
              <SelectContent>
                {(suppliers?.data ?? []).map((supplier) => (
                  <SelectItem key={supplier.id} value={supplier.id}>
                    {supplier.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="receipt-date">
              {t("purchasing.receipts.field.date")}
            </Label>
            <Input
              id="receipt-date"
              type="date"
              value={receiptDate}
              onChange={(event) => setReceiptDate(event.target.value)}
            />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="receipt-notes">
              {t("purchasing.receipts.field.notes")}
            </Label>
            <Input
              id="receipt-notes"
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
            />
          </div>
          {lines.map((line, index) => {
            const item = itemRows.find((row) => row.id === line.itemId)
            const linePreview = preview(line)
            return (
              <div key={line.key} className="grid gap-2 rounded-md border p-3">
                <div className="grid gap-1.5">
                  <Label>{t("purchasing.receipts.field.item")}</Label>
                  <SearchableSelect
                    aria-label={`${t("purchasing.receipts.field.item")} ${index + 1}`}
                    value={line.itemId}
                    placeholder={t("purchasing.receipts.chooseItem")}
                    searchLabel={t("purchasing.receipts.field.itemSearch")}
                    options={itemRows.map((row) => ({
                      value: row.id,
                      label: `${row.sku} · ${row.name}`,
                    }))}
                    onValueChange={(itemId) =>
                      setLines((current) =>
                        current.map((row) =>
                          row.key === line.key ? { ...row, itemId } : row,
                        ),
                      )
                    }
                  />
                </div>
                <p className="text-sm text-muted-foreground">
                  {t("purchasing.receipts.field.unit")}:{" "}
                  {item ? t(UNIT_LABELS[item.purchase_unit]) : "—"}
                </p>
                <div className="grid grid-cols-2 gap-2">
                  <div className="grid content-between gap-1.5">
                    <Label>{t("purchasing.receipts.field.quantity")}</Label>
                    <Input
                      aria-label={`${t("purchasing.receipts.field.quantity")} ${index + 1}`}
                      inputMode="decimal"
                      value={line.quantity}
                      onChange={(event) =>
                        setLines((current) =>
                          current.map((row) =>
                            row.key === line.key
                              ? { ...row, quantity: event.target.value }
                              : row,
                          ),
                        )
                      }
                    />
                  </div>
                  <div className="grid content-between gap-1.5">
                    <Label>{t("purchasing.receipts.field.cost")}</Label>
                    <Input
                      aria-label={`${t("purchasing.receipts.field.cost")} ${index + 1}`}
                      inputMode="decimal"
                      value={formatAmountInput(line.cost)}
                      onChange={(event) => {
                        const cost = parseAmountInput(event.target.value)
                        setLines((current) =>
                          current.map((row) =>
                            row.key === line.key ? { ...row, cost } : row,
                          ),
                        )
                      }}
                    />
                  </div>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span>
                    {t("purchasing.receipts.field.preview")}:{" "}
                    {linePreview == null ? "—" : formatMoney(linePreview)}
                  </span>
                  {lines.length > 1 && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      aria-label={t("common.delete")}
                      onClick={() =>
                        setLines((current) =>
                          current.filter((row) => row.key !== line.key),
                        )
                      }
                    >
                      <Trash2 className="size-4" />
                    </Button>
                  )}
                </div>
              </div>
            )
          })}
          <Button
            type="button"
            variant="outline"
            onClick={() => setLines((current) => [...current, emptyLine()])}
          >
            <Plus className="size-4" />
            {t("purchasing.receipts.addLine")}
          </Button>
          <p className="text-xs text-muted-foreground">
            {t("purchasing.receipts.previewNote")}
          </p>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t("common.cancel")}
          </Button>
          <LoadingButton
            loading={save.isPending}
            disabled={!valid}
            onClick={() => save.mutate()}
          >
            {t("common.save")}
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
