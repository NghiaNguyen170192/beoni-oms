import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import type { ColumnDef } from "@tanstack/react-table"
import { type FormEvent, useCallback, useMemo, useState } from "react"

import {
  AccountingService,
  type ApiError,
  type ExpensePaymentStatus,
  type ExpensePublic,
} from "@/client"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
import { DataTable } from "@/components/Common/DataTable"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
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
import { Skeleton } from "@/components/ui/skeleton"
import useAuth from "@/hooks/useAuth"
import { useFormatters } from "@/hooks/useBusinessSettings"
import useCustomToast from "@/hooks/useCustomToast"
import { t as translate, useI18n } from "@/i18n"
import { useIdempotencyKey } from "@/lib/idempotency"
import { hasPermission, requirePermission } from "@/lib/permissions"
import { handleError } from "@/utils"

export const Route = createFileRoute("/_layout/expenses")({
  component: Expenses,
  beforeLoad: requirePermission("expenses:read"),
  head: () => ({
    meta: [{ title: `${translate("accounting.expenses.title")} - Beoni OMS` }],
  }),
})

function todayInput(): string {
  const now = new Date()
  const pad = (value: number) => String(value).padStart(2, "0")
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

function Expenses() {
  const { t } = useI18n()
  const { user } = useAuth()
  const canManage = hasPermission(user, "expenses:manage")
  const { formatMoney, formatDateTime } = useFormatters()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const queryClient = useQueryClient()
  const recordKey = useIdempotencyKey()
  const payKey = useIdempotencyKey()
  const reverseKey = useIdempotencyKey()

  const [dateFrom, setDateFrom] = useState("")
  const [dateTo, setDateTo] = useState("")
  const [categoryId, setCategoryId] = useState("")
  const [paymentStatus, setPaymentStatus] = useState<string>("all")
  const [includeReversed, setIncludeReversed] = useState(false)
  const [creating, setCreating] = useState(false)
  const [paying, setPaying] = useState<ExpensePublic>()
  const [reversing, setReversing] = useState<ExpensePublic>()
  const [reason, setReason] = useState("")

  const [amount, setAmount] = useState("")
  const [expenseDate, setExpenseDate] = useState(todayInput)
  const [description, setDescription] = useState("")
  const [paidNow, setPaidNow] = useState(true)
  const [accountId, setAccountId] = useState("")
  const [formCategory, setFormCategory] = useState("")
  const [payDate, setPayDate] = useState(todayInput)
  const [payAccount, setPayAccount] = useState("")

  const categories = useQuery({
    queryKey: ["expense-categories"],
    queryFn: () => AccountingService.readCategories({ activeOnly: true }),
  })
  const accounts = useQuery({
    queryKey: ["money-accounts"],
    queryFn: () => AccountingService.readAccounts(),
    enabled: canManage,
  })
  const expenses = useQuery({
    queryKey: [
      "expenses",
      dateFrom,
      dateTo,
      categoryId,
      paymentStatus,
      includeReversed,
    ],
    queryFn: () =>
      AccountingService.readExpenses({
        dateFrom: dateFrom || undefined,
        dateTo: dateTo || undefined,
        categoryId: categoryId || undefined,
        paymentStatus:
          paymentStatus === "all"
            ? undefined
            : (paymentStatus as ExpensePaymentStatus),
        includeReversed,
      }),
  })

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["expenses"] })
    queryClient.invalidateQueries({ queryKey: ["money-accounts"] })
  }
  const onError = (err: ApiError) => handleError.call(showErrorToast, err)

  const create = useMutation({
    mutationFn: () =>
      AccountingService.createExpense({
        idempotencyKey: recordKey.current(),
        requestBody: {
          category_id: formCategory || categories.data![0].id,
          amount,
          expense_date: expenseDate,
          description: description.trim(),
          payment_status: paidNow ? "paid" : "unpaid",
          account_id: paidNow ? accountId || accounts.data!.data[0].id : null,
        },
      }),
    onSuccess: () => {
      showSuccessToast(t("accounting.expenses.recorded"))
      recordKey.reset()
      setCreating(false)
      setAmount("")
      setDescription("")
      refresh()
    },
    onError,
  })
  const pay = useMutation({
    mutationFn: () =>
      AccountingService.payExpense({
        expenseId: paying!.id,
        idempotencyKey: payKey.current(),
        requestBody: {
          account_id: payAccount || accounts.data!.data[0].id,
          payment_date: payDate,
        },
      }),
    onSuccess: () => {
      showSuccessToast(t("accounting.expenses.paid"))
      payKey.reset()
      setPaying(undefined)
      refresh()
    },
    onError,
  })
  const reverse = useMutation({
    mutationFn: () =>
      AccountingService.reverseExpense({
        expenseId: reversing!.id,
        idempotencyKey: reverseKey.current(),
        requestBody: { reason: reason.trim() },
      }),
    onSuccess: () => {
      showSuccessToast(t("accounting.expenses.reversed"))
      reverseKey.reset()
      setReversing(undefined)
      setReason("")
      refresh()
    },
    onError,
  })

  const categoryName = useCallback(
    (id: string) => categories.data?.find((row) => row.id === id)?.name ?? id,
    [categories.data],
  )

  const columns = useMemo<ColumnDef<ExpensePublic>[]>(
    () => [
      {
        accessorKey: "expense_date",
        header: () => translate("accounting.expenses.field.date"),
      },
      {
        id: "category",
        header: () => translate("accounting.expenses.field.category"),
        cell: ({ row }) => categoryName(row.original.category_id),
      },
      {
        accessorKey: "description",
        header: () => translate("accounting.expenses.field.description"),
      },
      {
        id: "amount",
        header: () => (
          <div className="text-right">
            {translate("accounting.expenses.field.amount")}
          </div>
        ),
        cell: ({ row }) => (
          <div className="text-right tabular-nums">
            {formatMoney(row.original.amount)}
          </div>
        ),
      },
      {
        id: "status",
        header: () => translate("common.status"),
        cell: ({ row }) =>
          row.original.status === "reversed"
            ? translate("accounting.expenses.status.reversed")
            : translate(
                `accounting.expenses.status.${row.original.payment_status}`,
              ),
      },
      {
        id: "actions",
        cell: ({ row }) =>
          canManage && row.original.status === "recorded" ? (
            <div className="flex justify-end gap-2">
              {row.original.payment_status === "unpaid" && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPaying(row.original)}
                >
                  {translate("accounting.expenses.pay")}
                </Button>
              )}
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setReversing(row.original)}
              >
                {translate("accounting.expenses.reverse")}
              </Button>
            </div>
          ) : row.original.paid_at ? (
            <span className="text-xs text-muted-foreground">
              {formatDateTime(row.original.paid_at)}
            </span>
          ) : null,
      },
    ],
    [canManage, categoryName, formatDateTime, formatMoney],
  )

  const rows = expenses.data?.data ?? []
  const submit = (event: FormEvent) => {
    event.preventDefault()
    create.mutate()
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold">
            {t("accounting.expenses.title")}
          </h1>
          <p className="text-sm text-muted-foreground">
            {t("accounting.expenses.description")}
          </p>
        </div>
        {canManage && (
          <Button onClick={() => setCreating(true)}>
            {t("accounting.expenses.add")}
          </Button>
        )}
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <div className="grid gap-1">
          <Label htmlFor="expense-from">{t("accounting.expenses.from")}</Label>
          <Input
            id="expense-from"
            type="date"
            value={dateFrom}
            onChange={(event) => setDateFrom(event.target.value)}
          />
        </div>
        <div className="grid gap-1">
          <Label htmlFor="expense-to">{t("accounting.expenses.to")}</Label>
          <Input
            id="expense-to"
            type="date"
            value={dateTo}
            onChange={(event) => setDateTo(event.target.value)}
          />
        </div>
        <div className="grid gap-1">
          <Label>{t("accounting.expenses.field.category")}</Label>
          <Select
            value={categoryId || "all"}
            onValueChange={(value) =>
              setCategoryId(value === "all" ? "" : value)
            }
          >
            <SelectTrigger className="w-48">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t("common.all")}</SelectItem>
              {categories.data?.map((category) => (
                <SelectItem key={category.id} value={category.id}>
                  {category.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="grid gap-1">
          <Label>{t("accounting.expenses.field.payment")}</Label>
          <Select value={paymentStatus} onValueChange={setPaymentStatus}>
            <SelectTrigger className="w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t("common.all")}</SelectItem>
              <SelectItem value="paid">
                {t("accounting.expenses.status.paid")}
              </SelectItem>
              <SelectItem value="unpaid">
                {t("accounting.expenses.status.unpaid")}
              </SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-center gap-2 pb-2 text-sm">
          <Checkbox
            id="include-reversed"
            checked={includeReversed}
            onCheckedChange={(checked) => setIncludeReversed(checked === true)}
          />
          <Label htmlFor="include-reversed">
            {t("accounting.expenses.includeReversed")}
          </Label>
        </div>
      </div>
      {expenses.data && expenses.data.totals.length > 0 && (
        <div>
          <h2 className="mb-2 text-sm font-medium">
            {t("accounting.expenses.totals")}
          </h2>
          <ul className="flex flex-wrap gap-3 text-sm">
            {expenses.data.totals.map((total) => (
              <li
                key={total.category_id}
                className="rounded-md border px-3 py-2"
              >
                {total.category_name}
                <span className="ml-2 tabular-nums">
                  {formatMoney(total.total)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {expenses.isPending ? (
        <Skeleton className="h-40" />
      ) : rows.length === 0 ? (
        <p className="text-muted-foreground">
          {t("accounting.expenses.empty")}
        </p>
      ) : (
        <DataTable columns={columns} data={rows} />
      )}

      <Dialog open={creating} onOpenChange={setCreating}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("accounting.expenses.add")}</DialogTitle>
          </DialogHeader>
          <form className="flex flex-col gap-3" onSubmit={submit}>
            <div className="grid gap-1">
              <Label>{t("accounting.expenses.field.category")}</Label>
              <Select
                value={formCategory || undefined}
                onValueChange={setFormCategory}
              >
                <SelectTrigger data-testid="expense-category">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {categories.data?.map((category) => (
                    <SelectItem key={category.id} value={category.id}>
                      {category.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1">
              <Label htmlFor="expense-amount">
                {t("accounting.expenses.field.amount")}
              </Label>
              <Input
                id="expense-amount"
                data-testid="expense-amount"
                inputMode="decimal"
                value={amount}
                onChange={(event) => setAmount(event.target.value)}
                required
              />
            </div>
            <div className="grid gap-1">
              <Label htmlFor="expense-date">
                {t("accounting.expenses.field.date")}
              </Label>
              <Input
                id="expense-date"
                type="date"
                value={expenseDate}
                onChange={(event) => setExpenseDate(event.target.value)}
                required
              />
            </div>
            <div className="grid gap-1">
              <Label htmlFor="expense-description">
                {t("accounting.expenses.field.description")}
              </Label>
              <Input
                id="expense-description"
                data-testid="expense-description"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                required
              />
            </div>
            <div className="flex items-center gap-2 text-sm">
              <Checkbox
                id="expense-paid-now"
                checked={paidNow}
                onCheckedChange={(checked) => setPaidNow(checked === true)}
              />
              <Label htmlFor="expense-paid-now">
                {t("accounting.expenses.paidNow")}
              </Label>
            </div>
            {paidNow && (
              <div className="grid gap-1">
                <Label>{t("accounting.expenses.field.account")}</Label>
                <Select
                  value={accountId || undefined}
                  onValueChange={setAccountId}
                >
                  <SelectTrigger data-testid="expense-account">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {accounts.data?.data.map((account) => (
                      <SelectItem key={account.id} value={account.id}>
                        {account.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setCreating(false)}
              >
                {t("common.cancel")}
              </Button>
              <LoadingButton
                type="submit"
                data-testid="save-expense"
                loading={create.isPending}
              >
                {t("common.save")}
              </LoadingButton>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog
        open={paying != null}
        onOpenChange={(open) => !open && setPaying(undefined)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("accounting.expenses.pay")}</DialogTitle>
          </DialogHeader>
          <form
            className="flex flex-col gap-3"
            onSubmit={(event) => {
              event.preventDefault()
              pay.mutate()
            }}
          >
            <div className="grid gap-1">
              <Label htmlFor="pay-date">
                {t("accounting.expenses.field.paidOn")}
              </Label>
              <Input
                id="pay-date"
                type="date"
                value={payDate}
                onChange={(event) => setPayDate(event.target.value)}
                required
              />
            </div>
            <div className="grid gap-1">
              <Label>{t("accounting.expenses.field.account")}</Label>
              <Select
                value={payAccount || undefined}
                onValueChange={setPayAccount}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {accounts.data?.data.map((account) => (
                    <SelectItem key={account.id} value={account.id}>
                      {account.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <DialogFooter>
              <LoadingButton type="submit" loading={pay.isPending}>
                {t("accounting.expenses.pay")}
              </LoadingButton>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={reversing != null}
        onOpenChange={(open) => {
          if (!open) setReversing(undefined)
        }}
        title={t("accounting.expenses.reverseTitle")}
        description={t("accounting.expenses.reverseDescription")}
        confirmLabel={t("accounting.expenses.reverse")}
        destructive
        loading={reverse.isPending}
        disabled={!reason.trim()}
        onConfirm={() => reverse.mutate()}
      >
        <div className="grid gap-1.5">
          <Label htmlFor="expense-reason">
            {t("accounting.expenses.reason")}
          </Label>
          <Input
            id="expense-reason"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
        </div>
      </ConfirmDialog>
    </div>
  )
}
