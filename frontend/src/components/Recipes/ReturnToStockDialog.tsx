import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { type FormEvent, useState } from "react"

import { type ApiError, type OrderPublic, OrdersService } from "@/client"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
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
import useCustomToast from "@/hooks/useCustomToast"
import { useI18n } from "@/i18n"
import { formatNumber } from "@/lib/format"
import { useIdempotencyKey } from "@/lib/idempotency"
import { handleError } from "@/utils"

type Draft = { quantity: string; sellable: boolean }

export function ReturnToStockDialog({
  order,
  open,
  onOpenChange,
}: {
  order: OrderPublic
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const { t } = useI18n()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const queryClient = useQueryClient()
  const idempotencyKey = useIdempotencyKey()
  const [reason, setReason] = useState("")
  const [drafts, setDrafts] = useState<Record<string, Draft>>({})

  const returns = useQuery({
    queryKey: ["stock-returns", order.id],
    queryFn: () => OrdersService.readStockReturns({ orderId: order.id }),
    enabled: open,
  })

  const returned = new Map<string, number>()
  for (const stockReturn of returns.data?.data ?? []) {
    for (const line of stockReturn.lines) {
      returned.set(
        line.order_line_id,
        (returned.get(line.order_line_id) ?? 0) + Number(line.quantity),
      )
    }
  }

  const bottles = order.lines.filter(
    (line) => line.product_type === "direct_sale",
  )

  const record = useMutation({
    mutationFn: (
      lines: { order_line_id: string; quantity: string; sellable: boolean }[],
    ) =>
      OrdersService.createStockReturn({
        orderId: order.id,
        idempotencyKey: idempotencyKey.current(),
        requestBody: { reason: reason.trim(), lines },
      }),
    onSuccess: () => {
      showSuccessToast(t("recipes.return.recorded"))
      idempotencyKey.reset()
      setReason("")
      setDrafts({})
      onOpenChange(false)
      queryClient.invalidateQueries({ queryKey: ["stock-returns", order.id] })
      queryClient.invalidateQueries({ queryKey: ["inventoryItems"] })
    },
    onError: (err: ApiError) => handleError.call(showErrorToast, err),
  })

  const submit = (event: FormEvent) => {
    event.preventDefault()
    const lines = bottles.flatMap((line) => {
      const draft = drafts[line.id]
      if (!draft || Number(draft.quantity) <= 0) return []
      return [
        {
          order_line_id: line.id,
          quantity: draft.quantity,
          sellable: draft.sellable,
        },
      ]
    })
    record.mutate(lines)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="return-stock-dialog">
        <DialogHeader>
          <DialogTitle>{t("recipes.return.title")}</DialogTitle>
          <DialogDescription>
            {t("recipes.return.description")}
          </DialogDescription>
        </DialogHeader>
        <form className="flex flex-col gap-4" onSubmit={submit}>
          {bottles.length === 0 && (
            <p className="text-sm text-muted-foreground">
              {t("recipes.return.none")}
            </p>
          )}
          {bottles.map((line) => {
            const remaining =
              Number(line.quantity) - (returned.get(line.id) ?? 0)
            const draft = drafts[line.id] ?? { quantity: "", sellable: true }
            return (
              <div key={line.id} className="flex items-end gap-3">
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium">
                    {line.item_name}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {t("recipes.return.remaining", {
                      quantity: formatNumber(String(remaining)),
                    })}
                  </div>
                </div>
                <Input
                  aria-label={t("recipes.quantity")}
                  className="w-24"
                  inputMode="decimal"
                  value={draft.quantity}
                  disabled={remaining <= 0}
                  onChange={(event) =>
                    setDrafts((current) => ({
                      ...current,
                      [line.id]: { ...draft, quantity: event.target.value },
                    }))
                  }
                />
                <div className="flex items-center gap-2 pb-2 text-sm">
                  <Checkbox
                    id={`sellable-${line.id}`}
                    checked={draft.sellable}
                    onCheckedChange={(checked) =>
                      setDrafts((current) => ({
                        ...current,
                        [line.id]: { ...draft, sellable: checked === true },
                      }))
                    }
                  />
                  <Label htmlFor={`sellable-${line.id}`}>
                    {t("recipes.return.sellable")}
                  </Label>
                </div>
              </div>
            )
          })}
          <div className="flex flex-col gap-2">
            <Label htmlFor="return-reason">{t("recipes.return.reason")}</Label>
            <Input
              id="return-reason"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              required
            />
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              {t("common.cancel")}
            </Button>
            <LoadingButton type="submit" loading={record.isPending}>
              {t("recipes.return.action")}
            </LoadingButton>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
