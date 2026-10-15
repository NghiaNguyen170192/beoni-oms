import { useQuery } from "@tanstack/react-query"
import { createFileRoute, redirect } from "@tanstack/react-router"
import { Printer } from "lucide-react"

import { OrdersService } from "@/client"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { isLoggedIn } from "@/hooks/useAuth"
import { t as translate, useI18n } from "@/i18n"
import { formatDateTime, formatMoney, formatNumber } from "@/lib/format"
import { ORDER_TYPE_LABELS } from "@/lib/labels"
import { displayName } from "@/lib/permissions"

export const Route = createFileRoute("/receipt/$orderId")({
  component: Receipt,
  beforeLoad: async () => {
    if (!isLoggedIn()) {
      throw redirect({ to: "/login" })
    }
  },
  head: () => ({
    meta: [{ title: translate("ordering.receipt.pageTitle") }],
  }),
})

const PRINT_STYLES = `
@page { size: 80mm auto; margin: 4mm; }
@media print {
  html, body { background: white !important; color: black !important; }
}
`

function Receipt() {
  const { t } = useI18n()
  const { orderId } = Route.useParams()
  const { data, error } = useQuery({
    queryKey: ["orders", "receipt", orderId],
    queryFn: () => OrdersService.readReceipt({ orderId }),
    retry: false,
  })

  if (error) {
    return (
      <p className="p-8 text-center text-destructive">
        {t("ordering.receipt.unavailable")}
      </p>
    )
  }
  if (!data) {
    return <Skeleton className="mx-auto mt-8 h-96 w-80" />
  }

  const { order, currency_code: currency, timezone } = data
  const money = (value: string) => formatMoney(value, currency)
  const hasCashier = Boolean(order.cashier_name || order.cashier_email)
  const row = (label: string, value: string) => (
    <div className="flex justify-between">
      <span>{label}</span>
      <span className="tabular-nums">{value}</span>
    </div>
  )

  return (
    <div className="min-h-screen bg-muted/40 py-8 print:bg-white print:py-0">
      <style>{PRINT_STYLES}</style>
      <div className="mx-auto mb-4 flex w-80 justify-end print:hidden">
        <Button onClick={() => window.print()}>
          <Printer className="mr-2" />
          {t("ordering.receipt.print")}
        </Button>
      </div>
      <article
        className="mx-auto w-80 bg-white p-4 font-mono text-xs text-black shadow print:w-full print:p-0 print:shadow-none"
        aria-label={t("ordering.receipt.label")}
      >
        <header className="mb-3 text-center">
          <h1 className="text-base font-bold">{data.business_name}</h1>
          <p>{order.number}</p>
          <p>
            {formatDateTime(order.completed_at ?? order.created_at, timezone)}
          </p>
          <p>
            {t(ORDER_TYPE_LABELS[order.order_type])}
            {order.table_label && ` · ${order.table_label}`}
          </p>
          {hasCashier && (
            <p>
              {t("ordering.receipt.cashier", {
                name: displayName(order.cashier_name, order.cashier_email),
              })}
            </p>
          )}
        </header>

        <div className="border-y border-dashed border-black py-2">
          {order.lines.map((line) => (
            <div key={line.id} className="mb-1">
              <div>{line.item_name}</div>
              <div className="flex justify-between">
                <span className="tabular-nums">
                  {formatNumber(line.quantity, 3)} × {money(line.unit_price)}
                </span>
                <span className="tabular-nums">{money(line.line_total)}</span>
              </div>
              {Number(line.discount_amount) > 0 && (
                <div>
                  {t("ordering.receipt.inclDiscount", {
                    amount: money(line.discount_amount),
                  })}
                </div>
              )}
            </div>
          ))}
        </div>

        <div className="flex flex-col gap-0.5 py-2">
          {row(t("ordering.totals.subtotal"), money(order.subtotal))}
          {Number(order.discount_total) > 0 &&
            row(
              t("ordering.totals.discounts"),
              `−${money(order.discount_total)}`,
            )}
          {Number(order.tax_rate) > 0 &&
            row(
              t("ordering.totals.inclTax", {
                rate: formatNumber(order.tax_rate, 2),
              }),
              money(order.tax_total),
            )}
          <div className="mt-1 flex justify-between border-t border-dashed border-black pt-1 text-sm font-bold">
            <span>{t("ordering.totals.total")}</span>
            <span className="tabular-nums" data-testid="receipt-total">
              {money(order.total)}
            </span>
          </div>
        </div>
        <p className="mt-3 text-center">{t("ordering.receipt.thankYou")}</p>
      </article>
    </div>
  )
}
