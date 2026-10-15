import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import type { ColumnDef } from "@tanstack/react-table"
import { Eye, Plus, Undo2 } from "lucide-react"
import { useMemo, useState } from "react"

import {
  AccountingService,
  PurchasingService,
  type ReceiptPaymentStatus,
  type ReceiptStatus,
  type ReceiptSummary,
  type StockReceiptPublic,
} from "@/client"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
import { DataTable } from "@/components/Common/DataTable"
import { ReceiptDialog } from "@/components/Purchasing/ReceiptDialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Skeleton } from "@/components/ui/skeleton"
import useAuth from "@/hooks/useAuth"
import { useFormatters } from "@/hooks/useBusinessSettings"
import useCustomToast from "@/hooks/useCustomToast"
import { t as translate, useI18n } from "@/i18n"
import { useIdempotencyKey } from "@/lib/idempotency"
import { hasPermission, requirePermission } from "@/lib/permissions"
import { handleError } from "@/utils"

export const Route = createFileRoute("/_layout/stock-receipts")({
  component: StockReceipts,
  beforeLoad: requirePermission("purchasing:read"),
  head: () => ({
    meta: [{ title: `${translate("purchasing.receipts.title")} - Beoni OMS` }],
  }),
})

const ALL = "all"

function StatusBadge({ status }: { status: ReceiptStatus }) {
  const { t } = useI18n()
  return (
    <Badge variant="secondary">
      {t(`purchasing.receipts.status.${status}`)}
    </Badge>
  )
}

function PaymentBadge({ status }: { status: ReceiptPaymentStatus }) {
  const { t } = useI18n()
  return (
    <Badge variant="outline">
      {t(`purchasing.receipts.payment.${status}`)}
    </Badge>
  )
}

function StockReceipts() {
  const { t } = useI18n()
  const { user } = useAuth()
  const canManage = hasPermission(user, "purchasing:manage")
  const canPost = hasPermission(user, "purchasing:post")
  const canReverse = hasPermission(user, "purchasing:reverse")
  const { formatMoney } = useFormatters()
  const [search, setSearch] = useState("")
  const [status, setStatus] = useState<typeof ALL | ReceiptStatus>(ALL)
  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState<StockReceiptPublic>()
  const [detailId, setDetailId] = useState<string>()

  const { data, isPending } = useQuery({
    queryKey: ["receipts", search, status],
    queryFn: () =>
      PurchasingService.readReceipts({
        q: search.trim() || undefined,
        status: status === ALL ? undefined : status,
      }),
  })
  const receipts = data?.data ?? []

  const columns = useMemo<ColumnDef<ReceiptSummary>[]>(
    () => [
      {
        accessorKey: "reference",
        header: () => translate("purchasing.receipts.field.reference"),
      },
      {
        accessorKey: "supplier_name",
        header: () => translate("purchasing.receipts.field.supplier"),
      },
      {
        accessorKey: "receipt_date",
        header: () => translate("purchasing.receipts.field.date"),
      },
      {
        id: "status",
        enableSorting: false,
        header: () => translate("common.status"),
        cell: ({ row }) => <StatusBadge status={row.original.status} />,
      },
      {
        id: "payment",
        enableSorting: false,
        header: () => translate("purchasing.suppliers.paid"),
        cell: ({ row }) => (
          <PaymentBadge status={row.original.payment_status} />
        ),
      },
      {
        id: "total",
        accessorFn: (row) => Number(row.total_value),
        header: () => (
          <div className="text-right">
            {translate("purchasing.receipts.field.total")}
          </div>
        ),
        cell: ({ row }) => (
          <div className="text-right tabular-nums">
            {formatMoney(row.original.total_value)}
          </div>
        ),
      },
      {
        id: "actions",
        enableSorting: false,
        cell: ({ row }) => (
          <Button
            variant="ghost"
            size="icon"
            aria-label={row.original.reference}
            onClick={() => setDetailId(row.original.id)}
          >
            <Eye className="size-4" />
          </Button>
        ),
      },
    ],
    [formatMoney],
  )

  return (
    <div className="flex w-full flex-col gap-4">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold">
            {t("purchasing.receipts.title")}
          </h1>
          <p className="text-muted-foreground text-sm">
            {t("purchasing.receipts.description")}
          </p>
        </div>
        {canManage && (
          <Button onClick={() => setCreating(true)}>
            <Plus className="size-4" />
            {t("purchasing.receipts.add")}
          </Button>
        )}
      </div>
      <div className="flex flex-wrap gap-2">
        <Input
          aria-label={t("purchasing.receipts.search")}
          placeholder={t("purchasing.receipts.search")}
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          className="max-w-sm"
        />
        <Select
          value={status}
          onValueChange={(value) => setStatus(value as typeof status)}
        >
          <SelectTrigger className="w-40" aria-label={t("common.status")}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>{t("common.all")}</SelectItem>
            <SelectItem value="draft">
              {t("purchasing.receipts.status.draft")}
            </SelectItem>
            <SelectItem value="posted">
              {t("purchasing.receipts.status.posted")}
            </SelectItem>
            <SelectItem value="reversed">
              {t("purchasing.receipts.status.reversed")}
            </SelectItem>
          </SelectContent>
        </Select>
      </div>
      {isPending ? (
        <Skeleton className="h-40 w-full" />
      ) : receipts.length === 0 ? (
        <p className="text-muted-foreground">
          {t("purchasing.receipts.empty")}
        </p>
      ) : (
        <DataTable columns={columns} data={receipts} />
      )}
      <ReceiptDialog open={creating} onOpenChange={setCreating} />
      {editing && (
        <ReceiptDialog
          open
          onOpenChange={(open) => {
            if (!open) setEditing(undefined)
          }}
          receipt={editing}
        />
      )}
      <ReceiptDetail
        receiptId={detailId}
        canManage={canManage}
        canPost={canPost}
        canReverse={canReverse}
        onClose={() => setDetailId(undefined)}
        onEdit={(receipt) => {
          setDetailId(undefined)
          setEditing(receipt)
        }}
      />
    </div>
  )
}

function ReceiptDetail({
  receiptId,
  canManage,
  canPost,
  canReverse,
  onClose,
  onEdit,
}: {
  receiptId?: string
  canManage: boolean
  canPost: boolean
  canReverse: boolean
  onClose: () => void
  onEdit: (receipt: StockReceiptPublic) => void
}) {
  const { t } = useI18n()
  const { user } = useAuth()
  const canPayOnPost = hasPermission(user, "cash:view")
  const { formatMoney } = useFormatters()
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const postKey = useIdempotencyKey()
  const reverseKey = useIdempotencyKey()
  const [confirmPost, setConfirmPost] = useState(false)
  const [confirmReverse, setConfirmReverse] = useState(false)
  const [reason, setReason] = useState("")
  const [payAmount, setPayAmount] = useState("")
  const [payAccount, setPayAccount] = useState("")
  const accounts = useQuery({
    queryKey: ["money-accounts"],
    queryFn: () => AccountingService.readAccounts(),
    enabled: canPayOnPost,
  })
  const accountOptions = accounts.data?.data ?? []
  const defaultAccount =
    accountOptions.find((account) => account.kind === "bank") ??
    accountOptions[0]
  const selectedAccountId = payAccount || defaultAccount?.id || ""

  const { data: receipt } = useQuery({
    queryKey: ["receipt", receiptId],
    queryFn: () => PurchasingService.readReceipt({ receiptId: receiptId! }),
    enabled: receiptId != null,
  })

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["receipts"] })
    queryClient.invalidateQueries({ queryKey: ["receipt", receiptId] })
    queryClient.invalidateQueries({ queryKey: ["suppliers"] })
    queryClient.invalidateQueries({ queryKey: ["inventoryItems"] })
  }

  const post = useMutation({
    mutationFn: () => {
      const amount = payAmount.trim()
      return PurchasingService.postReceipt({
        receiptId: receiptId!,
        idempotencyKey: postKey.current(),
        requestBody:
          amount && canPayOnPost && selectedAccountId
            ? {
                payment_amount: amount,
                account_id: selectedAccountId,
              }
            : undefined,
      })
    },
    onSuccess: (body) => {
      showSuccessToast(
        t("purchasing.receipts.posted", { reference: body.reference }),
      )
      postKey.reset()
      setConfirmPost(false)
      setPayAmount("")
      setPayAccount("")
      refresh()
    },
    onError: handleError.bind(showErrorToast),
  })

  const reverse = useMutation({
    mutationFn: () =>
      PurchasingService.reverseReceipt({
        receiptId: receiptId!,
        idempotencyKey: reverseKey.current(),
        requestBody: { reason },
      }),
    onSuccess: (body) => {
      showSuccessToast(
        t("purchasing.receipts.reversed", { reference: body.reference }),
      )
      reverseKey.reset()
      setConfirmReverse(false)
      setReason("")
      refresh()
    },
    onError: handleError.bind(showErrorToast),
  })

  const remove = useMutation({
    mutationFn: () =>
      PurchasingService.deleteReceipt({ receiptId: receiptId! }),
    onSuccess: () => {
      showSuccessToast(t("purchasing.receipts.deleted"))
      refresh()
      onClose()
    },
    onError: handleError.bind(showErrorToast),
  })

  return (
    <>
      <Sheet
        open={receiptId != null}
        onOpenChange={(open) => !open && onClose()}
      >
        <SheetContent className="sm:max-w-lg overflow-y-auto">
          {receipt && (
            <>
              <SheetHeader>
                <SheetTitle>{receipt.reference}</SheetTitle>
              </SheetHeader>
              <div className="flex flex-col gap-4 px-4 pb-6">
                <div className="flex gap-2">
                  <StatusBadge status={receipt.status} />
                  <PaymentBadge status={receipt.payment_status} />
                </div>
                <div>
                  <p className="text-sm">
                    {receipt.supplier_name} · {receipt.receipt_date}
                  </p>
                  <p className="text-right text-lg font-medium tabular-nums">
                    {formatMoney(receipt.total_value)}
                  </p>
                </div>
                <ul className="space-y-2 text-sm">
                  {receipt.lines.map((line) => (
                    <li key={line.id} className="flex justify-between gap-2">
                      <span>
                        {line.item_name} · {line.purchase_qty}{" "}
                        {line.purchase_unit}
                      </span>
                      <span className="tabular-nums">
                        {formatMoney(line.line_total)}
                      </span>
                    </li>
                  ))}
                </ul>
                <div className="flex flex-wrap gap-2">
                  {receipt.status === "draft" && canManage && (
                    <Button variant="outline" onClick={() => onEdit(receipt)}>
                      {t("common.edit")}
                    </Button>
                  )}
                  {receipt.status === "draft" && canPost && (
                    <Button onClick={() => setConfirmPost(true)}>
                      {t("purchasing.receipts.post")}
                    </Button>
                  )}
                  {receipt.status === "posted" &&
                    !receipt.reversal_of_id &&
                    canReverse && (
                      <Button
                        variant="outline"
                        onClick={() => setConfirmReverse(true)}
                      >
                        <Undo2 className="size-4" />
                        {t("purchasing.receipts.reverse")}
                      </Button>
                    )}
                  {receipt.status === "draft" && canManage && (
                    <Button
                      variant="ghost"
                      onClick={() => remove.mutate()}
                      disabled={remove.isPending}
                    >
                      {t("purchasing.receipts.deleteDraft")}
                    </Button>
                  )}
                </div>
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>
      <ConfirmDialog
        open={confirmPost}
        onOpenChange={setConfirmPost}
        title={t("purchasing.receipts.postTitle")}
        description={t("purchasing.receipts.postDescription")}
        confirmLabel={t("purchasing.receipts.post")}
        loading={post.isPending}
        onConfirm={() => post.mutate()}
      >
        {canPayOnPost && (
          <div className="grid gap-3">
            <div className="grid gap-1.5">
              <Label htmlFor="receipt-pay-amount">
                {t("accounting.receipts.payAmount")}
              </Label>
              <Input
                id="receipt-pay-amount"
                data-testid="receipt-pay-amount"
                inputMode="decimal"
                value={payAmount}
                onChange={(event) => setPayAmount(event.target.value)}
              />
            </div>
            <div className="grid gap-1.5">
              <Label>{t("accounting.receipts.payAccount")}</Label>
              <Select
                value={selectedAccountId || undefined}
                onValueChange={setPayAccount}
              >
                <SelectTrigger data-testid="receipt-pay-account">
                  <SelectValue
                    placeholder={
                      accountOptions.length === 0
                        ? t("common.loading")
                        : undefined
                    }
                  />
                </SelectTrigger>
                <SelectContent>
                  {accountOptions.map((account) => (
                    <SelectItem key={account.id} value={account.id}>
                      {account.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        )}
      </ConfirmDialog>
      <ConfirmDialog
        open={confirmReverse}
        onOpenChange={setConfirmReverse}
        title={t("purchasing.receipts.reverseTitle")}
        description={t("purchasing.receipts.reverseDescription")}
        confirmLabel={t("purchasing.receipts.reverse")}
        loading={reverse.isPending}
        destructive
        disabled={!reason.trim()}
        onConfirm={() => reverse.mutate()}
      >
        <div className="grid gap-1.5">
          <Label htmlFor="reverse-reason">
            {t("purchasing.receipts.reason")}
          </Label>
          <Input
            id="reverse-reason"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
        </div>
      </ConfirmDialog>
    </>
  )
}
