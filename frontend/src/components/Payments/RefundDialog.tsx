import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { type FormEvent, useState } from "react"

import { type ApiError, type OrderPublic, PaymentsService } from "@/client"
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
import { useFormatters } from "@/hooks/useBusinessSettings"
import useCustomToast from "@/hooks/useCustomToast"
import { type MessageKey, useI18n } from "@/i18n"
import { useIdempotencyKey } from "@/lib/idempotency"
import { handleError } from "@/utils"

interface RefundDialogProps {
  order: OrderPublic
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function RefundDialog({ order, open, onOpenChange }: RefundDialogProps) {
  const { t } = useI18n()
  const { formatMoney } = useFormatters()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const queryClient = useQueryClient()
  const idempotencyKey = useIdempotencyKey()
  const [methodId, setMethodId] = useState("")
  const [amount, setAmount] = useState("")
  const [reason, setReason] = useState("")

  const methods = useQuery({
    queryKey: ["payment-methods", "active"],
    queryFn: () => PaymentsService.readPaymentMethods({ activeOnly: true }),
    enabled: open,
  })
  const summary = useQuery({
    queryKey: ["order-payments", order.id],
    queryFn: () => PaymentsService.readOrderPayments({ orderId: order.id }),
    enabled: open,
  })

  const refund = useMutation({
    mutationFn: () =>
      PaymentsService.createOrderRefund({
        orderId: order.id,
        idempotencyKey: idempotencyKey.current(),
        requestBody: {
          method_id: methodId || methods.data!.data[0].id,
          amount,
          reason: reason.trim(),
        },
      }),
    onSuccess: () => {
      showSuccessToast(t("payments.refund.recorded"))
      idempotencyKey.reset()
      setAmount("")
      setReason("")
      onOpenChange(false)
      queryClient.invalidateQueries({ queryKey: ["orders"] })
      queryClient.invalidateQueries({ queryKey: ["order-payments", order.id] })
    },
    onError: (err: ApiError) => handleError.call(showErrorToast, err),
  })

  const submit = (event: FormEvent) => {
    event.preventDefault()
    refund.mutate()
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {t("payments.refund.title", { number: order.number })}
          </DialogTitle>
          <DialogDescription>
            {t("payments.refund.description")}
          </DialogDescription>
        </DialogHeader>
        <form className="flex flex-col gap-3" onSubmit={submit}>
          {summary.data && (
            <p className="text-sm text-muted-foreground">
              {t("payments.refund.paid", {
                amount: formatMoney(summary.data.paid_amount),
              })}
              {" · "}
              {t("payments.refund.already", {
                amount: formatMoney(summary.data.refunded_amount),
              })}
            </p>
          )}
          <div className="grid gap-1.5">
            <Label>{t("payments.refund.method")}</Label>
            <Select
              value={methodId || methods.data?.data[0]?.id}
              onValueChange={setMethodId}
            >
              <SelectTrigger className="h-12">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {methods.data?.data.map((method) => (
                  <SelectItem key={method.id} value={method.id}>
                    {method.name ||
                      t(`payments.kind.${method.kind}` as MessageKey)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="refund-amount">{t("payments.refund.amount")}</Label>
            <Input
              id="refund-amount"
              className="h-12"
              inputMode="decimal"
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
              required
            />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="refund-reason">{t("payments.refund.reason")}</Label>
            <Input
              id="refund-reason"
              className="h-12"
              maxLength={255}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              required
            />
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              className="h-12"
              onClick={() => onOpenChange(false)}
            >
              {t("common.cancel")}
            </Button>
            <LoadingButton
              type="submit"
              className="h-12"
              loading={refund.isPending}
              disabled={!reason.trim() || !amount}
            >
              {t("payments.refund.confirm")}
            </LoadingButton>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
