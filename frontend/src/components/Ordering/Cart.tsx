import { Minus, Percent, Plus, Trash2 } from "lucide-react"

import type { OrderLinePublic, OrderPublic, OrderType } from "@/client"
import type { FinishedGoodAvailability } from "@/components/Production/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useFormatters } from "@/hooks/useBusinessSettings"
import { useI18n } from "@/i18n"
import { formatNumber } from "@/lib/format"
import { ORDER_TYPE_LABELS, ORDER_TYPES } from "@/lib/labels"
import { OrderTotals } from "./OrderTotals"

interface CartProps {
  order: OrderPublic | null
  orderType: OrderType
  tableLabel: string
  busy: boolean
  canDiscount: boolean
  availability: Record<string, FinishedGoodAvailability>
  onOrderTypeChange: (type: OrderType) => void
  onTableLabelChange: (label: string) => void
  onTableLabelCommit: () => void
  onQuantityChange: (line: OrderLinePublic, quantity: number) => void
  onRemove: (line: OrderLinePublic) => void
  onLineDiscount: (line: OrderLinePublic) => void
}

export function Cart({
  order,
  orderType,
  tableLabel,
  busy,
  canDiscount,
  availability,
  onOrderTypeChange,
  onTableLabelChange,
  onTableLabelCommit,
  onQuantityChange,
  onRemove,
  onLineDiscount,
}: CartProps) {
  const { t } = useI18n()
  const { formatMoney } = useFormatters()
  const lines = order?.lines ?? []

  return (
    <div className="flex flex-col gap-4">
      <div
        className="grid grid-cols-3 gap-2"
        role="radiogroup"
        aria-label={t("ordering.cart.orderType")}
      >
        {ORDER_TYPES.map((type) => (
          <Button
            key={type}
            type="button"
            role="radio"
            aria-checked={orderType === type}
            variant={orderType === type ? "default" : "outline"}
            disabled={busy}
            onClick={() => onOrderTypeChange(type)}
            className="h-11"
          >
            {t(ORDER_TYPE_LABELS[type])}
          </Button>
        ))}
      </div>
      {orderType === "dine_in" && (
        <Input
          aria-label={t("ordering.cart.table")}
          placeholder={t("ordering.cart.table")}
          maxLength={50}
          value={tableLabel}
          onChange={(e) => onTableLabelChange(e.target.value)}
          onBlur={onTableLabelCommit}
        />
      )}

      {lines.length === 0 ? (
        <p className="py-10 text-center text-sm text-muted-foreground">
          {t("ordering.cart.empty")}
        </p>
      ) : (
        <ul
          className="flex flex-col divide-y"
          aria-label={t("ordering.cart.label")}
        >
          {lines.map((line) => {
            const quantity = Number(line.quantity)
            return (
              <li
                key={line.id}
                className="flex flex-col gap-2 py-3"
                data-testid="cart-line"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="font-medium leading-tight">
                      {line.item_name}
                    </div>
                    <div className="text-xs text-muted-foreground tabular-nums">
                      {formatMoney(line.unit_price)}
                      {Number(line.discount_amount) > 0 &&
                        ` · −${formatMoney(line.discount_amount)}`}
                    </div>
                    {availability[line.menu_item_id] && (
                      <div className="text-xs text-muted-foreground">
                        {t("ordering.stock.onHand", {
                          quantity: formatNumber(
                            availability[line.menu_item_id].available_quantity,
                          ),
                          unit: t(
                            `unit.${availability[line.menu_item_id].unit}`,
                          ),
                        })}
                      </div>
                    )}
                  </div>
                  <span className="tabular-nums font-medium">
                    {formatMoney(line.line_total)}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="icon"
                    aria-label={t("ordering.cart.decrease", {
                      name: line.item_name,
                    })}
                    disabled={busy || quantity <= 1}
                    onClick={() => onQuantityChange(line, quantity - 1)}
                  >
                    <Minus />
                  </Button>
                  <span
                    className="w-10 text-center tabular-nums"
                    data-testid="cart-line-quantity"
                  >
                    {formatNumber(line.quantity, 3)}
                  </span>
                  <Button
                    variant="outline"
                    size="icon"
                    aria-label={t("ordering.cart.increase", {
                      name: line.item_name,
                    })}
                    disabled={busy}
                    onClick={() => onQuantityChange(line, quantity + 1)}
                  >
                    <Plus />
                  </Button>
                  <div className="ml-auto flex gap-1">
                    {canDiscount && (
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label={t("ordering.cart.discount", {
                          name: line.item_name,
                        })}
                        disabled={busy}
                        onClick={() => onLineDiscount(line)}
                      >
                        <Percent />
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={t("ordering.cart.remove", {
                        name: line.item_name,
                      })}
                      disabled={busy}
                      onClick={() => onRemove(line)}
                    >
                      <Trash2 />
                    </Button>
                  </div>
                </div>
              </li>
            )
          })}
        </ul>
      )}

      {order && lines.length > 0 && <OrderTotals order={order} />}
    </div>
  )
}
