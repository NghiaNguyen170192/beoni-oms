import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { type FormEvent, useState } from "react"

import { AccountingService, type ApiError } from "@/client"
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import useCustomToast from "@/hooks/useCustomToast"
import { useI18n } from "@/i18n"
import { useIdempotencyKey } from "@/lib/idempotency"
import { handleError } from "@/utils"

function todayInput(): string {
  const now = new Date()
  const pad = (value: number) => String(value).padStart(2, "0")
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

export function SupplierPaymentDialog({
  supplierId,
  open,
  onOpenChange,
}: {
  supplierId: string
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const { t } = useI18n()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const queryClient = useQueryClient()
  const idempotencyKey = useIdempotencyKey()
  const [amount, setAmount] = useState("")
  const [paymentDate, setPaymentDate] = useState(todayInput)
  const [accountId, setAccountId] = useState("")
  const [reference, setReference] = useState("")

  const accounts = useQuery({
    queryKey: ["money-accounts"],
    queryFn: () => AccountingService.readAccounts(),
    enabled: open,
  })

  const pay = useMutation({
    mutationFn: () =>
      AccountingService.createSupplierPayment({
        idempotencyKey: idempotencyKey.current(),
        requestBody: {
          supplier_id: supplierId,
          amount,
          payment_date: paymentDate,
          account_id: accountId || accounts.data!.data[0].id,
          reference: reference.trim() || null,
        },
      }),
    onSuccess: () => {
      showSuccessToast(t("accounting.suppliers.paid"))
      idempotencyKey.reset()
      setAmount("")
      setReference("")
      onOpenChange(false)
      queryClient.invalidateQueries({ queryKey: ["suppliers"] })
      queryClient.invalidateQueries({ queryKey: ["supplier", supplierId] })
      queryClient.invalidateQueries({
        queryKey: ["supplier-statement", supplierId],
      })
      queryClient.invalidateQueries({ queryKey: ["money-accounts"] })
    },
    onError: (err: ApiError) => handleError.call(showErrorToast, err),
  })

  const submit = (event: FormEvent) => {
    event.preventDefault()
    pay.mutate()
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="supplier-payment-dialog">
        <DialogHeader>
          <DialogTitle>{t("accounting.suppliers.pay")}</DialogTitle>
        </DialogHeader>
        <form className="flex flex-col gap-3" onSubmit={submit}>
          <div className="grid gap-1">
            <Label htmlFor="supplier-pay-amount">
              {t("accounting.suppliers.field.amount")}
            </Label>
            <Input
              id="supplier-pay-amount"
              data-testid="supplier-pay-amount"
              inputMode="decimal"
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
              required
            />
          </div>
          <div className="grid gap-1">
            <Label htmlFor="supplier-pay-date">
              {t("accounting.suppliers.field.date")}
            </Label>
            <Input
              id="supplier-pay-date"
              type="date"
              value={paymentDate}
              onChange={(event) => setPaymentDate(event.target.value)}
              required
            />
          </div>
          <div className="grid gap-1">
            <Label>{t("accounting.suppliers.field.account")}</Label>
            <Select value={accountId || undefined} onValueChange={setAccountId}>
              <SelectTrigger data-testid="supplier-pay-account">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {accounts.data?.data.map((account) => (
                  <SelectItem key={account.id} value={account.id}>
                    {t(`accounting.account.kind.${account.kind}`)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-1">
            <Label htmlFor="supplier-pay-reference">
              {t("accounting.suppliers.field.reference")}
            </Label>
            <Input
              id="supplier-pay-reference"
              value={reference}
              onChange={(event) => setReference(event.target.value)}
            />
          </div>
          <DialogFooter>
            <LoadingButton
              type="submit"
              data-testid="save-supplier-payment"
              loading={pay.isPending}
            >
              {t("accounting.suppliers.pay")}
            </LoadingButton>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
