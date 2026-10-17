import type { OrderPublic, OrderStatus } from "@/client"
import { Badge } from "@/components/ui/badge"
import { useFormatters } from "@/hooks/useBusinessSettings"
import { useI18n } from "@/i18n"
import { formatNumber } from "@/lib/format"
import { ORDER_STATUS_LABELS } from "@/lib/labels"
import { cn } from "@/lib/utils"
import badgeStyles from "@/styles/badge.module.css"

const orderStatusClassMap: Record<OrderStatus, string> = {
  draft: badgeStyles.blue,
  confirmed: badgeStyles.yellow,
  paid: badgeStyles.green,
  completed: badgeStyles.green,
  cancelled: badgeStyles.red,
  partially_refunded: badgeStyles.yellow,
  refunded: badgeStyles.red,
}

export function OrderStatusBadge({ status }: { status: OrderStatus }) {
  const { t } = useI18n()
  return (
    <Badge className={orderStatusClassMap[status]}>
      {t(ORDER_STATUS_LABELS[status])}
    </Badge>
  )
}

/** Totals exactly as calculated by the backend. */
export function OrderTotals({
  order,
  className,
}: {
  order: OrderPublic
  className?: string
}) {
  const { t } = useI18n()
  const { formatMoney } = useFormatters()
  const row = (label: string, value: string, testId: string) => (
    <div className="flex justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span className="tabular-nums" data-testid={testId}>
        {value}
      </span>
    </div>
  )

  return (
    <div className={cn("flex flex-col gap-1 text-sm", className)}>
      {row(
        t("ordering.totals.subtotal"),
        formatMoney(order.subtotal),
        "order-subtotal",
      )}
      {Number(order.discount_total) > 0 &&
        row(
          t("ordering.totals.discount"),
          `−${formatMoney(order.discount_total)}`,
          "order-discount",
        )}
      {Number(order.tax_rate) > 0 &&
        row(
          t("ordering.totals.inclTax", {
            rate: formatNumber(order.tax_rate, 2),
          }),
          formatMoney(order.tax_total),
          "order-tax",
        )}
      <div className="flex justify-between text-base font-semibold pt-1 border-t mt-1">
        <span>{t("ordering.totals.total")}</span>
        <span className="tabular-nums" data-testid="order-total">
          {formatMoney(order.total)}
        </span>
      </div>
    </div>
  )
}
