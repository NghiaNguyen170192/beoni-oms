import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { CheckCircle2, Percent, Printer, XCircle } from "lucide-react"
import { useEffect, useState } from "react"

import {
  type ApiError,
  type DiscountUpdate,
  type MenuItemPublic,
  type OrderLineInput,
  type OrderLinePublic,
  type OrderPublic,
  OrdersService,
  type OrderType,
} from "@/client"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
import { Cart } from "@/components/Ordering/Cart"
import { DiscountDialog } from "@/components/Ordering/DiscountDialog"
import { MenuGrid } from "@/components/Ordering/MenuGrid"
import { PaymentDialog } from "@/components/Payments/PaymentDialog"
import { ShortageDialog } from "@/components/Recipes/ShortageDialog"
import { type Shortage, shortagesFrom } from "@/components/Recipes/shortages"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { LoadingButton } from "@/components/ui/loading-button"
import useAuth from "@/hooks/useAuth"
import { useFormatters } from "@/hooks/useBusinessSettings"
import useCustomToast from "@/hooks/useCustomToast"
import { t as translate, useI18n } from "@/i18n"
import { useIdempotencyKey } from "@/lib/idempotency"
import { hasPermission, requirePermission } from "@/lib/permissions"
import { handleError } from "@/utils"

export const Route = createFileRoute("/_layout/pos")({
  component: Pos,
  beforeLoad: requirePermission("ordering:create"),
  head: () => ({
    meta: [{ title: translate("ordering.pos.pageTitle") }],
  }),
})

const CURRENT_ORDER_KEY = "pos.currentOrderId"
const OPEN_STATUSES = ["draft", "confirmed"]

type DiscountTarget =
  | { kind: "order" }
  | { kind: "line"; line: OrderLinePublic }

function toInput(line: OrderLinePublic): OrderLineInput {
  return {
    id: line.id,
    menu_item_id: line.menu_item_id,
    quantity: line.quantity,
    note: line.note,
  }
}

function Pos() {
  const { t } = useI18n()
  const { user } = useAuth()
  const canDiscount = hasPermission(user, "ordering:discount")
  const canCancel = hasPermission(user, "ordering:cancel")
  const queryClient = useQueryClient()
  const { formatMoney } = useFormatters()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const completeKey = useIdempotencyKey()

  const [order, setOrder] = useState<OrderPublic | null>(null)
  const [orderType, setOrderType] = useState<OrderType>("takeaway")
  const [tableLabel, setTableLabel] = useState("")
  const [discountTarget, setDiscountTarget] = useState<DiscountTarget>()
  const [cancelling, setCancelling] = useState(false)
  const [cancelReason, setCancelReason] = useState("")
  const [completed, setCompleted] = useState<OrderPublic>()
  const [paying, setPaying] = useState(false)
  const [shortages, setShortages] = useState<Shortage[]>()

  const onError = (err: ApiError) => {
    const missing = shortagesFrom(err)
    if (missing) {
      setShortages(missing)
      return
    }
    handleError.call(showErrorToast, err)
  }

  const storedId = localStorage.getItem(CURRENT_ORDER_KEY)
  const { data: resumed } = useQuery({
    queryKey: ["orders", "pos-resume", storedId],
    queryFn: () => OrdersService.readOrder({ orderId: storedId! }),
    enabled: storedId !== null && order === null,
    retry: false,
    staleTime: Number.POSITIVE_INFINITY,
  })

  useEffect(() => {
    if (!resumed || order) return
    if (OPEN_STATUSES.includes(resumed.status)) {
      setOrder(resumed)
      setOrderType(resumed.order_type)
      setTableLabel(resumed.table_label ?? "")
    } else {
      localStorage.removeItem(CURRENT_ORDER_KEY)
    }
  }, [resumed, order])

  const adopt = (next: OrderPublic) => {
    if (next.id !== order?.id) {
      localStorage.setItem(CURRENT_ORDER_KEY, next.id)
    }
    completeKey.reset()
    setOrder(next)
  }

  const resetCart = () => {
    localStorage.removeItem(CURRENT_ORDER_KEY)
    completeKey.reset()
    setOrder(null)
    setTableLabel("")
    setCancelReason("")
  }

  const saveLines = useMutation({
    mutationFn: (lines: OrderLineInput[]) =>
      order
        ? OrdersService.replaceOrderLines({
            orderId: order.id,
            requestBody: { lines },
          })
        : OrdersService.createOrder({
            requestBody: {
              order_type: orderType,
              table_label:
                orderType === "dine_in" ? tableLabel.trim() || null : null,
              lines,
            },
          }),
    onSuccess: adopt,
    onError,
  })

  const updateOrder = useMutation({
    mutationFn: (body: { order_type: OrderType; table_label: string | null }) =>
      OrdersService.updateOrder({ orderId: order!.id, requestBody: body }),
    onSuccess: adopt,
    onError,
  })

  const discount = useMutation({
    mutationFn: ({
      target,
      body,
    }: {
      target: DiscountTarget
      body: DiscountUpdate
    }) =>
      target.kind === "order"
        ? OrdersService.setOrderDiscount({
            orderId: order!.id,
            requestBody: body,
          })
        : OrdersService.setLineDiscount({
            orderId: order!.id,
            lineId: target.line.id,
            requestBody: body,
          }),
    onSuccess: (next) => {
      adopt(next)
      setDiscountTarget(undefined)
    },
    onError,
  })

  const cancel = useMutation({
    mutationFn: () =>
      OrdersService.cancelOrder({
        orderId: order!.id,
        requestBody: { reason: cancelReason.trim() },
      }),
    onSuccess: () => {
      showSuccessToast(t("ordering.pos.cancelled"))
      setCancelling(false)
      resetCart()
    },
    onError,
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["orders"] }),
  })

  const complete = useMutation({
    mutationFn: () =>
      OrdersService.completeOrder({
        orderId: order!.id,
        idempotencyKey: completeKey.current(),
      }),
    onSuccess: (done) => {
      showSuccessToast(t("ordering.pos.completed", { number: done.number }))
      resetCart()
      setCompleted(done)
    },
    onError,
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["orders"] }),
  })

  const busy =
    saveLines.isPending ||
    updateOrder.isPending ||
    discount.isPending ||
    cancel.isPending ||
    complete.isPending

  const currentLines = order?.lines.map(toInput) ?? []

  const addItem = (item: MenuItemPublic) => {
    setCompleted(undefined)
    const existing = order?.lines.find(
      (line) => line.menu_item_id === item.id && !line.discount_type,
    )
    const lines = existing
      ? currentLines.map((line) =>
          line.id === existing.id
            ? { ...line, quantity: String(Number(existing.quantity) + 1) }
            : line,
        )
      : [...currentLines, { menu_item_id: item.id, quantity: "1" }]
    saveLines.mutate(lines)
  }

  const changeQuantity = (target: OrderLinePublic, quantity: number) =>
    saveLines.mutate(
      currentLines.map((line) =>
        line.id === target.id ? { ...line, quantity: String(quantity) } : line,
      ),
    )

  const removeLine = (target: OrderLinePublic) =>
    saveLines.mutate(currentLines.filter((line) => line.id !== target.id))

  const changeOrderType = (type: OrderType) => {
    setOrderType(type)
    if (order && order.order_type !== type) {
      updateOrder.mutate({
        order_type: type,
        table_label: type === "dine_in" ? tableLabel.trim() || null : null,
      })
    }
  }

  const commitTableLabel = () => {
    const label = tableLabel.trim() || null
    if (
      order &&
      order.order_type === "dine_in" &&
      order.table_label !== label
    ) {
      updateOrder.mutate({ order_type: "dine_in", table_label: label })
    }
  }

  const discountCurrent =
    discountTarget?.kind === "line"
      ? {
          type: discountTarget.line.discount_type,
          value: discountTarget.line.discount_value,
        }
      : {
          type: order?.order_discount_type ?? null,
          value: order?.order_discount_value ?? null,
        }

  const hasLines = (order?.lines.length ?? 0) > 0

  return (
    <div className="grid gap-6 md:grid-cols-[1fr_340px] lg:grid-cols-[1fr_380px]">
      <div className="flex flex-col gap-4">
        <h1 className="text-2xl font-bold tracking-tight">
          {t("ordering.pos.title")}
        </h1>
        <MenuGrid onAdd={addItem} disabled={busy} />
      </div>

      <Card className="h-fit md:sticky md:top-20">
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>{order ? order.number : t("ordering.pos.newOrder")}</span>
            {canDiscount && hasLines && (
              <Button
                variant="outline"
                size="sm"
                disabled={busy}
                onClick={() => setDiscountTarget({ kind: "order" })}
              >
                <Percent className="mr-1" />
                {t("ordering.pos.orderDiscount")}
              </Button>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {completed && !order && (
            <div
              className="flex flex-col gap-3 rounded-md border border-green-600/40 bg-green-600/10 p-3"
              data-testid="order-completed"
            >
              <div className="flex items-center gap-2 font-medium">
                <CheckCircle2 className="size-5 text-green-600" />
                {completed.number} · {formatMoney(completed.total)}
              </div>
              <Button variant="outline" asChild>
                <Link
                  to="/receipt/$orderId"
                  params={{ orderId: completed.id }}
                  target="_blank"
                >
                  <Printer className="mr-2" />
                  {t("ordering.pos.printReceipt")}
                </Link>
              </Button>
            </div>
          )}

          <Cart
            order={order}
            orderType={orderType}
            tableLabel={tableLabel}
            busy={busy}
            canDiscount={canDiscount}
            onOrderTypeChange={changeOrderType}
            onTableLabelChange={setTableLabel}
            onTableLabelCommit={commitTableLabel}
            onQuantityChange={changeQuantity}
            onRemove={removeLine}
            onLineDiscount={(line) => setDiscountTarget({ kind: "line", line })}
          />

          <div className="flex gap-2">
            {order && canCancel && (
              <Button
                variant="outline"
                className="h-12"
                disabled={busy}
                onClick={() => setCancelling(true)}
              >
                <XCircle className="mr-1" />
                {t("ordering.pos.cancel")}
              </Button>
            )}
            <LoadingButton
              className="h-12 flex-1 text-base"
              disabled={!hasLines || (busy && !complete.isPending)}
              loading={complete.isPending}
              onClick={() => {
                if (order && Number(order.total) === 0) {
                  complete.mutate()
                } else {
                  setPaying(true)
                }
              }}
            >
              {t("ordering.pos.complete")}
            </LoadingButton>
          </div>
        </CardContent>
      </Card>

      {canDiscount && (
        <DiscountDialog
          open={discountTarget !== undefined}
          onOpenChange={(open) => !open && setDiscountTarget(undefined)}
          title={
            discountTarget?.kind === "line"
              ? t("ordering.pos.lineDiscountTitle", {
                  name: discountTarget.line.item_name,
                })
              : t("ordering.pos.orderDiscount")
          }
          current={discountCurrent}
          loading={discount.isPending}
          onApply={(body) =>
            discountTarget && discount.mutate({ target: discountTarget, body })
          }
        />
      )}

      {order && (
        <PaymentDialog
          order={order}
          open={paying}
          onOpenChange={setPaying}
          onCompleted={(done) => {
            resetCart()
            setCompleted(done)
          }}
          onShortage={setShortages}
        />
      )}

      <ShortageDialog
        shortages={shortages}
        onClose={() => setShortages(undefined)}
      />

      <ConfirmDialog
        open={cancelling}
        onOpenChange={setCancelling}
        title={t("ordering.pos.cancelTitle", { number: order?.number ?? "" })}
        description={t("ordering.pos.cancelDescription")}
        confirmLabel={t("ordering.pos.cancelConfirm")}
        destructive
        disabled={!cancelReason.trim()}
        loading={cancel.isPending}
        onConfirm={() => cancel.mutate()}
      >
        <div className="grid gap-1.5">
          <Label htmlFor="cancel-reason">
            {t("ordering.pos.cancelReason")}
          </Label>
          <Input
            id="cancel-reason"
            maxLength={255}
            value={cancelReason}
            onChange={(e) => setCancelReason(e.target.value)}
          />
        </div>
      </ConfirmDialog>
    </div>
  )
}
