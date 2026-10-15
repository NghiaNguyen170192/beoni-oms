import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import type { ColumnDef } from "@tanstack/react-table"
import { Pencil, Plus } from "lucide-react"
import { useMemo, useState } from "react"

import {
  AccountingService,
  PurchasingService,
  type ReceiptSummary,
  type SupplierPublic,
} from "@/client"
import { SupplierPaymentDialog } from "@/components/Accounting/SupplierPaymentDialog"
import { DataTable } from "@/components/Common/DataTable"
import { SupplierDialog } from "@/components/Purchasing/SupplierDialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Skeleton } from "@/components/ui/skeleton"
import useAuth from "@/hooks/useAuth"
import { useFormatters } from "@/hooks/useBusinessSettings"
import { t as translate, useI18n } from "@/i18n"
import { hasPermission, requirePermission } from "@/lib/permissions"

export const Route = createFileRoute("/_layout/suppliers")({
  component: Suppliers,
  beforeLoad: requirePermission("purchasing:read"),
  head: () => ({
    meta: [{ title: `${translate("purchasing.suppliers.title")} - Beoni OMS` }],
  }),
})

function Suppliers() {
  const { t } = useI18n()
  const { user } = useAuth()
  const canManage = hasPermission(user, "purchasing:manage")
  const { formatMoney } = useFormatters()
  const [search, setSearch] = useState("")
  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState<SupplierPublic>()
  const [detailId, setDetailId] = useState<string>()

  const { data, isPending } = useQuery({
    queryKey: ["suppliers", search],
    queryFn: () =>
      PurchasingService.readSuppliers({ q: search.trim() || undefined }),
  })
  const suppliers = data?.data ?? []
  const detail = suppliers.find((row) => row.id === detailId)

  const columns = useMemo<ColumnDef<SupplierPublic>[]>(
    () => [
      {
        accessorKey: "name",
        header: () => translate("purchasing.suppliers.field.name"),
        cell: ({ row }) => (
          <button
            type="button"
            className="font-medium text-left hover:underline"
            onClick={() => setDetailId(row.original.id)}
          >
            {row.original.name}
          </button>
        ),
      },
      {
        accessorKey: "phone",
        header: () => translate("purchasing.suppliers.field.phone"),
        cell: ({ row }) => row.original.phone || "—",
      },
      {
        id: "outstanding",
        header: () => (
          <div className="text-right">
            {translate("purchasing.suppliers.outstanding")}
          </div>
        ),
        cell: ({ row }) => (
          <div className="text-right tabular-nums">
            {formatMoney(row.original.outstanding)}
          </div>
        ),
      },
      {
        id: "status",
        header: () => translate("common.status"),
        cell: ({ row }) =>
          row.original.is_active ? (
            <Badge variant="secondary">{translate("common.active")}</Badge>
          ) : (
            <Badge variant="outline">{translate("common.inactive")}</Badge>
          ),
      },
      {
        id: "actions",
        cell: ({ row }) =>
          canManage ? (
            <Button
              variant="ghost"
              size="icon"
              aria-label={`${translate("common.edit")} ${row.original.name}`}
              onClick={() => setEditing(row.original)}
            >
              <Pencil className="size-4" />
            </Button>
          ) : null,
      },
    ],
    [canManage, formatMoney],
  )

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold">
            {t("purchasing.suppliers.title")}
          </h1>
          <p className="text-muted-foreground text-sm">
            {t("purchasing.suppliers.description")}
          </p>
        </div>
        {canManage && (
          <Button onClick={() => setCreating(true)}>
            <Plus className="size-4" />
            {t("purchasing.suppliers.add")}
          </Button>
        )}
      </div>
      <Input
        aria-label={t("purchasing.suppliers.search")}
        placeholder={t("purchasing.suppliers.search")}
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        className="max-w-sm"
      />
      {isPending ? (
        <Skeleton className="h-40 w-full" />
      ) : suppliers.length === 0 ? (
        <p className="text-muted-foreground">
          {t("purchasing.suppliers.empty")}
        </p>
      ) : (
        <DataTable columns={columns} data={suppliers} />
      )}
      <SupplierDialog open={creating} onOpenChange={setCreating} />
      <SupplierDialog
        open={editing != null}
        onOpenChange={(open) => {
          if (!open) setEditing(undefined)
        }}
        supplier={editing}
      />
      <SupplierDetail
        supplier={detail}
        onClose={() => setDetailId(undefined)}
      />
    </div>
  )
}

function SupplierDetail({
  supplier,
  onClose,
}: {
  supplier?: SupplierPublic
  onClose: () => void
}) {
  const { t } = useI18n()
  const { user } = useAuth()
  const { formatMoney, formatDateTime } = useFormatters()
  const canPay = hasPermission(user, "supplier_payments:record")
  const canStatement = hasPermission(user, "supplier_payments:read")
  const [paying, setPaying] = useState(false)
  const { data } = useQuery({
    queryKey: ["supplierReceipts", supplier?.id],
    queryFn: () =>
      PurchasingService.readSupplierReceipts({ supplierId: supplier!.id }),
    enabled: supplier != null,
  })
  const statement = useQuery({
    queryKey: ["supplier-statement", supplier?.id],
    queryFn: () =>
      AccountingService.readStatement({ supplierId: supplier!.id }),
    enabled: supplier != null && canStatement,
  })
  const history = data?.data ?? []

  return (
    <Sheet open={supplier != null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="sm:max-w-lg overflow-y-auto">
        {supplier && (
          <>
            <SheetHeader>
              <SheetTitle>{supplier.name}</SheetTitle>
            </SheetHeader>
            <dl className="mt-4 grid grid-cols-2 gap-2 text-sm">
              <dt>{t("purchasing.suppliers.payables")}</dt>
              <dd className="text-right tabular-nums">
                {formatMoney(supplier.payables_total)}
              </dd>
              <dt>{t("purchasing.suppliers.paid")}</dt>
              <dd className="text-right tabular-nums">
                {formatMoney(supplier.paid_total)}
              </dd>
              <dt className="font-medium">
                {t("purchasing.suppliers.outstanding")}
              </dt>
              <dd
                className="text-right font-medium tabular-nums"
                data-testid="supplier-outstanding"
              >
                {formatMoney(supplier.outstanding)}
              </dd>
            </dl>
            {canPay && (
              <Button className="mt-4" onClick={() => setPaying(true)}>
                {t("accounting.suppliers.pay")}
              </Button>
            )}
            {canStatement && (
              <>
                <h2 className="mt-6 mb-2 font-medium">
                  {t("accounting.suppliers.statement")}
                </h2>
                <ul
                  className="space-y-2 text-sm"
                  data-testid="supplier-statement"
                >
                  {statement.data?.data.map((row) => (
                    <li
                      key={`${row.kind}-${row.id}`}
                      className="flex justify-between gap-2"
                    >
                      <span>
                        {t(
                          row.kind === "payment"
                            ? "accounting.suppliers.kind.payment"
                            : "accounting.suppliers.kind.receipt",
                        )}
                        {" · "}
                        {formatDateTime(row.occurred_at)}
                        {row.reference ? ` · ${row.reference}` : ""}
                      </span>
                      <span className="tabular-nums">
                        {formatMoney(
                          row.kind === "payment" ? row.payments : row.purchases,
                        )}
                      </span>
                    </li>
                  ))}
                </ul>
              </>
            )}
            <h2 className="mt-6 mb-2 font-medium">
              {t("purchasing.suppliers.history")}
            </h2>
            <ul className="space-y-2 text-sm">
              {history.map((row: ReceiptSummary) => (
                <li key={row.id} className="flex justify-between gap-2">
                  <span>
                    {row.reference} · {row.receipt_date} ·{" "}
                    {t(`purchasing.receipts.status.${row.status}`)}
                  </span>
                  <span className="tabular-nums">
                    {formatMoney(row.total_value)}
                  </span>
                </li>
              ))}
            </ul>
            <SupplierPaymentDialog
              supplierId={supplier.id}
              open={paying}
              onOpenChange={setPaying}
            />
          </>
        )}
      </SheetContent>
    </Sheet>
  )
}
