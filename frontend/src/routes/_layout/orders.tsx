import { useQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import type { ColumnDef } from "@tanstack/react-table"
import { Eye, Printer } from "lucide-react"
import { type FormEvent, useMemo, useState } from "react"

import {
  type OrderStatus,
  type OrderSummary,
  OrdersService,
  type OrderType,
} from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import {
  OrderStatusBadge,
  OrderTotals,
} from "@/components/Ordering/OrderTotals"
import { RefundDialog } from "@/components/Payments/RefundDialog"
import { ReturnToStockDialog } from "@/components/Recipes/ReturnToStockDialog"
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
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
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
import { type MessageKey, t as translate, useI18n } from "@/i18n"
import { formatNumber } from "@/lib/format"
import {
  ORDER_STATUS_LABELS,
  ORDER_STATUSES,
  ORDER_TYPE_LABELS,
  ORDER_TYPES,
} from "@/lib/labels"
import {
  displayName,
  hasPermission,
  requirePermission,
} from "@/lib/permissions"

export const Route = createFileRoute("/_layout/orders")({
  component: Orders,
  beforeLoad: requirePermission("ordering:view_own", "ordering:view_all"),
  head: () => ({
    meta: [{ title: translate("ordering.orders.pageTitle") }],
  }),
})

const ALL = "all"
const PAGE_SIZE = 100

type Filters = {
  number: string
  dateFrom: string
  dateTo: string
  status?: OrderStatus
  orderType?: OrderType
}

const EMPTY_FILTERS: Filters = { number: "", dateFrom: "", dateTo: "" }

const hasReceipt = (status: OrderStatus) =>
  status !== "draft" && status !== "cancelled"

function OrderDetail({
  orderId,
  onClose,
}: {
  orderId: string | undefined
  onClose: () => void
}) {
  const { t } = useI18n()
  const { user } = useAuth()
  const { formatMoney, formatDateTime } = useFormatters()
  const [refunding, setRefunding] = useState(false)
  const [returning, setReturning] = useState(false)
  const canRefund = hasPermission(user, "payments:refund")
  const canReturn = hasPermission(user, "inventory:return")
  const { data: order } = useQuery({
    queryKey: ["orders", "detail", orderId],
    queryFn: () => OrdersService.readOrder({ orderId: orderId! }),
    enabled: orderId !== undefined,
  })

  return (
    <Sheet open={orderId !== undefined} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="w-full sm:max-w-xl overflow-y-auto">
        {order ? (
          <>
            <SheetHeader>
              <SheetTitle className="flex items-center gap-2">
                {order.number} <OrderStatusBadge status={order.status} />
              </SheetTitle>
              <SheetDescription>
                {t(ORDER_TYPE_LABELS[order.order_type])}
                {order.table_label && ` · ${order.table_label}`} ·{" "}
                {formatDateTime(order.created_at)} ·{" "}
                {displayName(order.cashier_name, order.cashier_email)}
                {order.cancel_reason &&
                  ` · ${t("ordering.orders.cancelledReason", { reason: order.cancel_reason })}`}
              </SheetDescription>
            </SheetHeader>
            <div className="flex flex-col gap-4 px-4 pb-6">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t("ordering.orders.item")}</TableHead>
                    <TableHead className="text-right">
                      {t("ordering.orders.qty")}
                    </TableHead>
                    <TableHead className="text-right">
                      {t("ordering.orders.price")}
                    </TableHead>
                    <TableHead className="text-right">
                      {t("ordering.orders.amount")}
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {order.lines.map((line) => (
                    <TableRow key={line.id}>
                      <TableCell>
                        {line.item_name}
                        {(line.finished_good_allocations ?? []).map((allocation) => (
                          <div
                            key={allocation.finished_good_lot_id}
                            className="text-xs text-muted-foreground"
                          >
                            {allocation.lot_number}
                            {allocation.batch_number !== null &&
                              ` · ${t("recipes.return.batch", {
                                number: allocation.batch_number,
                              })}`}
                            {` · ${formatDateTime(allocation.finished_at)}`}
                          </div>
                        ))}
                        {Number(line.discount_amount) > 0 && (
                          <div className="text-xs text-muted-foreground">
                            {t("ordering.orders.lineDiscount", {
                              amount: formatMoney(line.discount_amount),
                            })}
                          </div>
                        )}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {formatNumber(line.quantity, 3)}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {formatMoney(line.unit_price)}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {formatMoney(line.line_total)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              <OrderTotals order={order} />
              {(order.status === "completed" ||
                order.status === "partially_refunded") &&
                canRefund && (
                  <Button className="w-fit" onClick={() => setRefunding(true)}>
                    {t("payments.refund.confirm")}
                  </Button>
                )}
              {(order.status === "completed" ||
                order.status === "partially_refunded" ||
                order.status === "refunded") &&
                canReturn &&
                order.lines.some(
                  (line) =>
                    (line.product_type === "direct_sale" &&
                      Boolean(line.recipe_version_id)) ||
                    (line.finished_good_allocations ?? []).length > 0,
                ) && (
                  <Button
                    variant="outline"
                    className="w-fit"
                    onClick={() => setReturning(true)}
                  >
                    {t("recipes.return.action")}
                  </Button>
                )}
              {hasReceipt(order.status) && (
                <Button variant="outline" asChild className="w-fit">
                  <Link
                    to="/receipt/$orderId"
                    params={{ orderId: order.id }}
                    target="_blank"
                  >
                    <Printer className="mr-2" />
                    {t("ordering.orders.receipt")}
                  </Link>
                </Button>
              )}
            </div>
            <RefundDialog
              order={order}
              open={refunding}
              onOpenChange={setRefunding}
            />
            <ReturnToStockDialog
              order={order}
              open={returning}
              onOpenChange={setReturning}
            />
          </>
        ) : (
          <Skeleton className="m-4 h-40" />
        )}
      </SheetContent>
    </Sheet>
  )
}

function Orders() {
  const { t } = useI18n()
  const { user } = useAuth()
  const viewAll = hasPermission(user, "ordering:view_all")
  const { formatMoney, formatDateTime } = useFormatters()

  const [draft, setDraft] = useState<Filters>(EMPTY_FILTERS)
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS)
  const [page, setPage] = useState(0)
  const [viewingId, setViewingId] = useState<string>()

  const { data, isPending } = useQuery({
    queryKey: ["orders", "list", filters, page],
    queryFn: () =>
      OrdersService.readOrders({
        number: filters.number.trim() || undefined,
        dateFrom: filters.dateFrom || undefined,
        dateTo: filters.dateTo || undefined,
        status: filters.status,
        orderType: filters.orderType,
        skip: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      }),
  })
  const pageCount = Math.max(1, Math.ceil((data?.count ?? 0) / PAGE_SIZE))

  const apply = (event: FormEvent) => {
    event.preventDefault()
    setFilters(draft)
    setPage(0)
  }

  const columns = useMemo<ColumnDef<OrderSummary>[]>(
    () => [
      {
        accessorKey: "number",
        header: () => translate("ordering.orders.number"),
        cell: ({ row }) => (
          <span className="font-medium">{row.original.number}</span>
        ),
      },
      {
        id: "created_at",
        accessorFn: (row) => row.created_at,
        header: () => translate("ordering.orders.created"),
        cell: ({ row }) => formatDateTime(row.original.created_at),
      },
      {
        id: "type",
        enableSorting: false,
        header: () => translate("ordering.orders.type"),
        cell: ({ row }) =>
          `${translate(ORDER_TYPE_LABELS[row.original.order_type])}${row.original.table_label ? ` · ${row.original.table_label}` : ""}`,
      },
      {
        id: "status",
        enableSorting: false,
        header: () => translate("common.status"),
        cell: ({ row }) => <OrderStatusBadge status={row.original.status} />,
      },
      {
        id: "cashier",
        enableSorting: false,
        header: () => translate("ordering.orders.cashier"),
        cell: ({ row }) =>
          displayName(row.original.cashier_name, row.original.cashier_email),
      },
      {
        id: "total",
        accessorFn: (row) => Number(row.total),
        header: () => (
          <div className="text-right">{translate("ordering.orders.total")}</div>
        ),
        cell: ({ row }) => (
          <div className="text-right tabular-nums">
            {formatMoney(row.original.total)}
          </div>
        ),
      },
      {
        id: "actions",
        enableSorting: false,
        header: () => (
          <span className="sr-only">{translate("common.actions")}</span>
        ),
        cell: ({ row }) => (
          <div className="flex justify-end gap-1">
            <Button
              variant="ghost"
              size="icon"
              aria-label={translate("ordering.orders.view", {
                number: row.original.number,
              })}
              onClick={() => setViewingId(row.original.id)}
            >
              <Eye />
            </Button>
            {hasReceipt(row.original.status) && (
              <Button
                variant="ghost"
                size="icon"
                aria-label={translate("ordering.orders.receiptFor", {
                  number: row.original.number,
                })}
                asChild
              >
                <Link
                  to="/receipt/$orderId"
                  params={{ orderId: row.original.id }}
                  target="_blank"
                >
                  <Printer />
                </Link>
              </Button>
            )}
          </div>
        ),
      },
    ],
    [formatDateTime, formatMoney],
  )

  const enumSelect = <T extends string>(
    label: string,
    value: T | undefined,
    options: readonly T[],
    labels: Record<T, MessageKey>,
    onChange: (value: T | undefined) => void,
  ) => (
    <div className="grid gap-1.5">
      <Label>{label}</Label>
      <Select
        value={value ?? ALL}
        onValueChange={(next) =>
          onChange(next === ALL ? undefined : (next as T))
        }
      >
        <SelectTrigger
          className="w-40"
          aria-label={t("ordering.orders.filterLabel", { label })}
        >
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>{t("common.all")}</SelectItem>
          {options.map((option) => (
            <SelectItem key={option} value={option}>
              {t(labels[option])}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          {t("ordering.orders.title")}
        </h1>
        <p className="text-muted-foreground">
          {viewAll
            ? t("ordering.orders.allOrders")
            : t("ordering.orders.ownOrders")}
        </p>
      </div>

      <form onSubmit={apply} className="flex flex-wrap items-end gap-3">
        <div className="grid gap-1.5">
          <Label htmlFor="orders-number">{t("ordering.orders.number")}</Label>
          <Input
            id="orders-number"
            placeholder="HD-..."
            value={draft.number}
            onChange={(e) => setDraft({ ...draft, number: e.target.value })}
            className="w-44"
          />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="orders-from">{t("ordering.orders.from")}</Label>
          <Input
            id="orders-from"
            type="date"
            value={draft.dateFrom}
            onChange={(e) => setDraft({ ...draft, dateFrom: e.target.value })}
          />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="orders-to">{t("ordering.orders.to")}</Label>
          <Input
            id="orders-to"
            type="date"
            value={draft.dateTo}
            onChange={(e) => setDraft({ ...draft, dateTo: e.target.value })}
          />
        </div>
        {enumSelect(
          t("common.status"),
          draft.status,
          ORDER_STATUSES,
          ORDER_STATUS_LABELS,
          (status) => setDraft({ ...draft, status }),
        )}
        {enumSelect(
          t("ordering.orders.type"),
          draft.orderType,
          ORDER_TYPES,
          ORDER_TYPE_LABELS,
          (orderType) => setDraft({ ...draft, orderType }),
        )}
        <Button type="submit">{t("ordering.orders.filter")}</Button>
      </form>

      {isPending ? (
        <Skeleton className="h-40 w-full" />
      ) : (
        <DataTable columns={columns} data={data?.data ?? []} />
      )}
      {pageCount > 1 && (
        <div className="flex items-center justify-end gap-2 text-sm">
          <span className="text-muted-foreground">
            {t("ordering.orders.pagination", {
              count: data?.count ?? 0,
              page: page + 1,
              pages: pageCount,
            })}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page === 0}
            onClick={() => setPage(page - 1)}
          >
            {t("ordering.orders.newer")}
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={page + 1 >= pageCount}
            onClick={() => setPage(page + 1)}
          >
            {t("ordering.orders.older")}
          </Button>
        </div>
      )}

      <OrderDetail
        orderId={viewingId}
        onClose={() => setViewingId(undefined)}
      />
    </div>
  )
}
