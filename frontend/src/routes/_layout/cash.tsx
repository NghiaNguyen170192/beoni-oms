import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { type FormEvent, useState } from "react"

import { AccountingService, type ApiError } from "@/client"
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
import { type MessageKey, t as translate, useI18n } from "@/i18n"
import { formatAmountInput, parseAmountInput } from "@/lib/format"
import { useIdempotencyKey } from "@/lib/idempotency"
import { hasPermission, requirePermission } from "@/lib/permissions"
import { handleError } from "@/utils"

export const Route = createFileRoute("/_layout/cash")({
  component: Cash,
  beforeLoad: requirePermission("cash:view"),
  head: () => ({
    meta: [{ title: `${translate("accounting.cash.title")} - Beoni OMS` }],
  }),
})

function todayInput(): string {
  const now = new Date()
  const pad = (value: number) => String(value).padStart(2, "0")
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

const movementSourceLabels: Record<string, MessageKey> = {
  cash_adjustment: "accounting.cash.sourceType.cashAdjustment",
  cash_adjustment_reversal: "accounting.cash.sourceType.cashAdjustmentReversal",
  expense: "accounting.cash.sourceType.expense",
  expense_reversal: "accounting.cash.sourceType.expenseReversal",
  payment: "accounting.cash.sourceType.payment",
  payment_void: "accounting.cash.sourceType.paymentVoid",
  refund: "accounting.cash.sourceType.refund",
  supplier_payment: "accounting.cash.sourceType.supplierPayment",
  supplier_payment_reversal:
    "accounting.cash.sourceType.supplierPaymentReversal",
}

function Cash() {
  const { t } = useI18n()
  const { user } = useAuth()
  const canAdjust = hasPermission(user, "cash:adjust")
  const { formatMoney, formatDateTime } = useFormatters()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const queryClient = useQueryClient()
  const adjustKey = useIdempotencyKey()
  const [selectedId, setSelectedId] = useState<string>()
  const [dateFrom, setDateFrom] = useState(todayInput)
  const [dateTo, setDateTo] = useState(todayInput)
  const [adjusting, setAdjusting] = useState(false)
  const [amount, setAmount] = useState("")
  const [reason, setReason] = useState("")

  const accounts = useQuery({
    queryKey: ["money-accounts"],
    queryFn: () => AccountingService.readAccounts(),
  })
  const selected =
    accounts.data?.data.find((row) => row.id === selectedId) ??
    accounts.data?.data[0]

  const movements = useQuery({
    queryKey: ["cash-movements", selected?.id, dateFrom, dateTo],
    queryFn: () =>
      AccountingService.readMovements({
        accountId: selected!.id,
        dateFrom,
        dateTo,
      }),
    enabled: selected != null && Boolean(dateFrom) && Boolean(dateTo),
  })

  const adjust = useMutation({
    mutationFn: () =>
      AccountingService.createAdjustment({
        idempotencyKey: adjustKey.current(),
        requestBody: {
          account_id: selected!.id,
          amount,
          reason: reason.trim(),
        },
      }),
    onSuccess: () => {
      showSuccessToast(t("accounting.cash.adjusted"))
      adjustKey.reset()
      setAdjusting(false)
      setAmount("")
      setReason("")
      queryClient.invalidateQueries({ queryKey: ["money-accounts"] })
      queryClient.invalidateQueries({ queryKey: ["cash-movements"] })
    },
    onError: (err: ApiError) => handleError.call(showErrorToast, err),
  })

  const submit = (event: FormEvent) => {
    event.preventDefault()
    adjust.mutate()
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col items-start gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold">
            {t("accounting.cash.title")}
          </h1>
          <p className="text-sm text-muted-foreground">
            {t("accounting.cash.description")}
          </p>
        </div>
        {canAdjust && selected && (
          <Button
            className="w-full sm:w-auto"
            onClick={() => setAdjusting(true)}
          >
            {t("accounting.cash.adjust")}
          </Button>
        )}
      </div>
      {accounts.isPending ? (
        <Skeleton className="h-24" />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {accounts.data?.data.map((account) => (
            <button
              key={account.id}
              type="button"
              data-testid={`cash-account-${account.kind}`}
              className={`rounded-md border p-4 text-left ${
                selected?.id === account.id ? "border-primary" : ""
              }`}
              onClick={() => setSelectedId(account.id)}
            >
              <div className="text-sm text-muted-foreground">
                {t(`accounting.account.kind.${account.kind}`)}
              </div>
              <div className="text-xl font-semibold tabular-nums">
                {formatMoney(account.balance)}
              </div>
              <div className="text-xs uppercase tracking-wide text-muted-foreground">
                {t("accounting.cash.recorded")}
              </div>
              {account.kind === "bank" && (
                <div className="mt-1 text-xs text-muted-foreground">
                  {t("accounting.cash.defaultPay")}
                </div>
              )}
            </button>
          ))}
        </div>
      )}
      <div className="grid grid-cols-1 gap-3 sm:max-w-xl sm:grid-cols-2">
        <div className="grid min-w-0 gap-1">
          <Label htmlFor="cash-from">{t("accounting.expenses.from")}</Label>
          <Input
            id="cash-from"
            type="date"
            value={dateFrom}
            onChange={(event) => setDateFrom(event.target.value)}
          />
        </div>
        <div className="grid min-w-0 gap-1">
          <Label htmlFor="cash-to">{t("accounting.expenses.to")}</Label>
          <Input
            id="cash-to"
            type="date"
            value={dateTo}
            onChange={(event) => setDateTo(event.target.value)}
          />
        </div>
      </div>
      {movements.data && (
        <div className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
          {(
            [
              ["opening", movements.data.opening],
              ["inflows", movements.data.inflows],
              ["outflows", movements.data.outflows],
              ["closing", movements.data.closing],
            ] as const
          ).map(([key, value]) => (
            <div key={key} className="rounded-md bg-muted p-3">
              <div className="text-muted-foreground">
                {t(`accounting.cash.${key}`)}
              </div>
              <div
                className="tabular-nums font-medium"
                data-testid={`cash-${key}`}
              >
                {formatMoney(value)}
              </div>
            </div>
          ))}
        </div>
      )}
      {movements.isPending ? (
        <Skeleton className="h-32" />
      ) : movements.data && movements.data.data.length === 0 ? (
        <p className="text-muted-foreground">{t("accounting.cash.empty")}</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("accounting.cash.when")}</TableHead>
              <TableHead>{t("accounting.cash.source")}</TableHead>
              <TableHead className="text-right">
                {t("accounting.cash.amount")}
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {movements.data?.data.map((row) => (
              <TableRow key={row.id}>
                <TableCell>{formatDateTime(row.occurred_at)}</TableCell>
                <TableCell>
                  {movementSourceLabels[row.source_type]
                    ? t(movementSourceLabels[row.source_type])
                    : row.source_type}
                  {row.note ? ` · ${row.note}` : ""}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatMoney(row.amount)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      <Dialog open={adjusting} onOpenChange={setAdjusting}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("accounting.cash.adjust")}</DialogTitle>
          </DialogHeader>
          <form className="flex flex-col gap-3" onSubmit={submit}>
            <p className="text-sm text-muted-foreground">
              {selected?.name}. {t("accounting.cash.amountHint")}
            </p>
            <div className="grid gap-1">
              <Label htmlFor="adjust-amount">
                {t("accounting.cash.field.amount")}
              </Label>
              <Input
                id="adjust-amount"
                inputMode="decimal"
                value={formatAmountInput(amount)}
                onChange={(event) =>
                  setAmount(parseAmountInput(event.target.value))
                }
                required
              />
            </div>
            <div className="grid gap-1">
              <Label htmlFor="adjust-reason">
                {t("accounting.cash.field.reason")}
              </Label>
              <Input
                id="adjust-reason"
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                required
              />
            </div>
            <DialogFooter>
              <LoadingButton type="submit" loading={adjust.isPending}>
                {t("common.save")}
              </LoadingButton>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
