import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"

import {
  type ApiError,
  type OrderPublic,
  OrdersService,
  type PaymentMethodPublic,
  PaymentsService,
} from "@/client"
import { type Shortage, shortagesFrom } from "@/components/Recipes/shortages"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { LoadingButton } from "@/components/ui/loading-button"
import { useFormatters } from "@/hooks/useBusinessSettings"
import useCustomToast from "@/hooks/useCustomToast"
import { type MessageKey, useI18n } from "@/i18n"
import { useIdempotencyKey } from "@/lib/idempotency"
import { handleError } from "@/utils"

const QUICK = ["50000", "100000", "200000", "500000"]

function cents(value: string): number {
  const trimmed = value.trim()
  if (!/^\d+(\.\d{0,2})?$/.test(trimmed)) return 0
  const [whole, frac = ""] = trimmed.split(".")
  return Number(whole) * 100 + Number(`${frac}00`.slice(0, 2))
}

interface PaymentDialogProps {
  order: OrderPublic
  open: boolean
  onOpenChange: (open: boolean) => void
  onCompleted: (order: OrderPublic) => void
  onShortage?: (shortages: Shortage[]) => void
}

export function PaymentDialog({
  order,
  open,
  onOpenChange,
  onCompleted,
  onShortage,
}: PaymentDialogProps) {
  const { t } = useI18n()
  const { formatMoney } = useFormatters()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const queryClient = useQueryClient()
  const idempotencyKey = useIdempotencyKey()
  const [methodId, setMethodId] = useState<string>()
  const [digits, setDigits] = useState("")

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

  const selected =
    methods.data?.data.find((method) => method.id === methodId) ??
    methods.data?.data[0]
  const remaining = summary.data?.remaining ?? order.total
  const remainingCents = cents(remaining)
  const enteredCents = cents(digits)
  const isCash = selected?.kind === "cash"
  const covers =
    remainingCents === 0 ||
    (isCash
      ? enteredCents >= remainingCents && enteredCents > 0
      : enteredCents === 0 || enteredCents === remainingCents)
  const partial = enteredCents > 0 && enteredCents < remainingCents
  const changeCents =
    isCash && enteredCents > remainingCents ? enteredCents - remainingCents : 0

  const onError = (err: ApiError) => {
    const missing = shortagesFrom(err)
    if (missing && onShortage) {
      onOpenChange(false)
      onShortage(missing)
      return
    }
    handleError.call(showErrorToast, err)
  }

  const finish = useMutation({
    mutationFn: () =>
      remainingCents === 0
        ? OrdersService.completeOrder({
            orderId: order.id,
            idempotencyKey: idempotencyKey.current(),
          })
        : PaymentsService.payAndCompleteOrder({
            orderId: order.id,
            idempotencyKey: idempotencyKey.current(),
            requestBody: isCash
              ? { method_id: selected!.id, tendered: digits }
              : {
                  method_id: selected!.id,
                  amount: digits || remaining,
                },
          }),
    onSuccess: (done) => {
      showSuccessToast(t("ordering.pos.completed", { number: done.number }))
      onCompleted(done)
      onOpenChange(false)
    },
    onError,
  })

  const record = useMutation({
    mutationFn: () =>
      PaymentsService.createOrderPayment({
        orderId: order.id,
        idempotencyKey: idempotencyKey.current(),
        requestBody: isCash
          ? { method_id: selected!.id, tendered: digits }
          : { method_id: selected!.id, amount: digits },
      }),
    onSuccess: () => {
      idempotencyKey.reset()
      setDigits("")
      queryClient.invalidateQueries({ queryKey: ["order-payments", order.id] })
    },
    onError,
  })

  const pending = finish.isPending || record.isPending

  const push = (extra: string) => {
    const next = (digits + extra).replace(/^0+(?=\d)/, "")
    if (next.length <= 12) setDigits(next)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t("payments.pos.title")}</DialogTitle>
          <DialogDescription>{t("payments.pos.description")}</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-3">
          <div className="flex items-baseline justify-between">
            <span className="text-sm text-muted-foreground">
              {t("payments.pos.remaining")}
            </span>
            <span className="text-2xl font-semibold tabular-nums">
              {formatMoney(remaining)}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {methods.data?.data.map((method) => (
              <MethodButton
                key={method.id}
                method={method}
                selected={selected?.id === method.id}
                label={t(`payments.kind.${method.kind}` as MessageKey)}
                onSelect={() => {
                  setMethodId(method.id)
                  setDigits("")
                }}
              />
            ))}
          </div>
          {selected && remainingCents > 0 && (
            <>
              <div className="rounded-md border px-3 py-2 text-right text-xl tabular-nums">
                <div className="text-xs text-muted-foreground">
                  {isCash
                    ? t("payments.pos.tendered")
                    : t("payments.pos.amount")}
                </div>
                {digits || "0"}
              </div>
              {changeCents > 0 && (
                <p className="text-sm text-muted-foreground">
                  {t("payments.pos.changePreview", {
                    amount: formatMoney((changeCents / 100).toFixed(2)),
                  })}
                </p>
              )}
              <div className="grid grid-cols-3 gap-2">
                {["1", "2", "3", "4", "5", "6", "7", "8", "9", "000", "0"].map(
                  (key) => (
                    <Button
                      key={key}
                      type="button"
                      variant="outline"
                      className="h-12 text-lg"
                      onClick={() => push(key)}
                    >
                      {key}
                    </Button>
                  ),
                )}
                <Button
                  type="button"
                  variant="outline"
                  className="h-12"
                  aria-label={t("payments.pos.backspace")}
                  onClick={() => setDigits((value) => value.slice(0, -1))}
                >
                  ⌫
                </Button>
              </div>
              {isCash && (
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    variant="secondary"
                    className="h-10"
                    onClick={() => setDigits(String(remainingCents / 100))}
                  >
                    {formatMoney(remaining)}
                  </Button>
                  {QUICK.map((amount) => (
                    <Button
                      key={amount}
                      type="button"
                      variant="secondary"
                      className="h-10"
                      onClick={() => setDigits(amount)}
                    >
                      {formatMoney(amount)}
                    </Button>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
        <DialogFooter>
          {partial ? (
            <LoadingButton
              className="h-12 w-full"
              loading={record.isPending}
              disabled={pending || !selected}
              onClick={() => record.mutate()}
            >
              {t("payments.pos.record")}
            </LoadingButton>
          ) : (
            <LoadingButton
              className="h-12 w-full"
              loading={finish.isPending}
              disabled={pending || !selected || !covers}
              onClick={() => finish.mutate()}
            >
              {remainingCents === 0
                ? t("payments.pos.completePaid")
                : t("payments.pos.payAndComplete")}
            </LoadingButton>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function MethodButton({
  method,
  selected,
  label,
  onSelect,
}: {
  method: PaymentMethodPublic
  selected: boolean
  label: string
  onSelect: () => void
}) {
  return (
    <Button
      type="button"
      variant={selected ? "default" : "outline"}
      className="h-12"
      aria-pressed={selected}
      onClick={onSelect}
    >
      {method.name || label}
    </Button>
  )
}
