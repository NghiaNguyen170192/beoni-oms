import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import type { ColumnDef } from "@tanstack/react-table"
import { Eye, Undo2 } from "lucide-react"
import { useMemo, useState } from "react"

import {
  type AdjustmentStatus,
  type ApiError,
  InventoryService,
  type StockAdjustmentSummary,
} from "@/client"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
import { DataTable } from "@/components/Common/DataTable"
import { NewAdjustmentDialog } from "@/components/Inventory/NewAdjustmentDialog"
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
import useCustomToast from "@/hooks/useCustomToast"
import { t as translate, useI18n } from "@/i18n"
import { formatNumber } from "@/lib/format"
import { useIdempotencyKey } from "@/lib/idempotency"
import { ADJUSTMENT_REASON_LABELS, UNIT_LABELS } from "@/lib/labels"
import {
  displayName,
  hasPermission,
  requirePermission,
} from "@/lib/permissions"
import { handleError } from "@/utils"

export const Route = createFileRoute("/_layout/stock-adjustments")({
  component: StockAdjustments,
  beforeLoad: requirePermission("inventory:view"),
  head: () => ({
    meta: [
      { title: `${translate("inventory.adjustments.title")} - Beoni OMS` },
    ],
  }),
})

const ALL = "all"

function StatusBadge({ status }: { status: AdjustmentStatus }) {
  const { t } = useI18n()
  return status === "posted" ? (
    <Badge variant="secondary">{t("inventory.adjustments.posted")}</Badge>
  ) : (
    <Badge variant="outline">{t("inventory.adjustments.reversed")}</Badge>
  )
}

function AdjustmentDetail({
  adjustmentId,
  onClose,
}: {
  adjustmentId: string | undefined
  onClose: () => void
}) {
  const { t } = useI18n()
  const { formatDateTime, formatUnitCost } = useFormatters()
  const { data } = useQuery({
    queryKey: ["stockAdjustments", "detail", adjustmentId],
    queryFn: () =>
      InventoryService.readAdjustment({ adjustmentId: adjustmentId! }),
    enabled: adjustmentId !== undefined,
  })

  return (
    <Sheet
      open={adjustmentId !== undefined}
      onOpenChange={(open) => !open && onClose()}
    >
      <SheetContent className="w-full sm:max-w-3xl overflow-y-auto">
        {data ? (
          <>
            <SheetHeader>
              <SheetTitle className="flex items-center gap-2">
                {t("inventory.adjustments.detailTitle", {
                  number: data.number,
                })}{" "}
                <StatusBadge status={data.status} />
              </SheetTitle>
              <SheetDescription>
                {t("inventory.adjustments.postedByAt", {
                  time: formatDateTime(data.posted_at),
                  name: displayName(data.posted_by_name, data.posted_by_email),
                })}
                {data.note && ` · ${data.note}`}
                {data.reversed_at &&
                  ` · ${t("inventory.adjustments.reversedAt", {
                    time: formatDateTime(data.reversed_at),
                  })}${data.reversal_note ? `: ${data.reversal_note}` : ""}`}
              </SheetDescription>
            </SheetHeader>
            <div className="px-4 pb-6">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t("inventory.adjustments.item")}</TableHead>
                    <TableHead>{t("inventory.adjustments.reason")}</TableHead>
                    <TableHead className="text-right">
                      {t("inventory.adjustments.before")}
                    </TableHead>
                    <TableHead className="text-right">
                      {t("inventory.adjustments.change")}
                    </TableHead>
                    <TableHead className="text-right">
                      {t("inventory.adjustments.after")}
                    </TableHead>
                    <TableHead className="text-right">
                      {t("inventory.movements.unitCost")}
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.lines.map((line) => (
                    <TableRow key={line.id}>
                      <TableCell>
                        {line.item_sku} · {line.item_name}
                      </TableCell>
                      <TableCell>
                        {t(ADJUSTMENT_REASON_LABELS[line.reason])}
                        {line.counted_quantity !== null &&
                          ` ${t("inventory.adjustments.counted", {
                            quantity: formatNumber(line.counted_quantity),
                          })}`}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {formatNumber(line.previous_quantity)}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {Number(line.quantity_change) > 0 ? "+" : ""}
                        {formatNumber(line.quantity_change)}{" "}
                        {t(UNIT_LABELS[line.base_unit])}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {formatNumber(line.resulting_quantity)}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {formatUnitCost(line.unit_cost)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </>
        ) : (
          <Skeleton className="m-4 h-32" />
        )}
      </SheetContent>
    </Sheet>
  )
}

function StockAdjustments() {
  const { t } = useI18n()
  const { user } = useAuth()
  const canAdjust = hasPermission(user, "inventory:adjust")
  const canReverse = hasPermission(user, "inventory:reverse")
  const { formatDateTime } = useFormatters()
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const reverseKey = useIdempotencyKey()

  const [status, setStatus] = useState<AdjustmentStatus>()
  const [viewingId, setViewingId] = useState<string>()
  const [reversing, setReversing] = useState<StockAdjustmentSummary>()
  const [reversalNote, setReversalNote] = useState("")

  const { data, isPending } = useQuery({
    queryKey: ["stockAdjustments", "list", status],
    queryFn: () => InventoryService.readAdjustments({ status, limit: 200 }),
  })

  const closeReverse = () => {
    reverseKey.reset()
    setReversing(undefined)
    setReversalNote("")
  }

  const reverse = useMutation({
    mutationFn: (adjustment: StockAdjustmentSummary) =>
      InventoryService.reverseAdjustment({
        adjustmentId: adjustment.id,
        idempotencyKey: reverseKey.current(),
        requestBody: { note: reversalNote.trim() || null },
      }),
    onSuccess: (adjustment) => {
      showSuccessToast(
        t("inventory.adjustments.reversedToast", {
          number: adjustment.number,
        }),
      )
      closeReverse()
    },
    onError: (err: ApiError) => handleError.call(showErrorToast, err),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["stockAdjustments"] })
      queryClient.invalidateQueries({ queryKey: ["inventoryItems"] })
      queryClient.invalidateQueries({ queryKey: ["inventoryMovements"] })
    },
  })

  const columns = useMemo<ColumnDef<StockAdjustmentSummary>[]>(
    () => [
      {
        accessorKey: "number",
        header: () => translate("inventory.adjustments.number"),
        cell: ({ row }) => `#${row.original.number}`,
      },
      {
        id: "posted_at",
        accessorFn: (row) => row.posted_at,
        header: () => translate("inventory.adjustments.postedAt"),
        cell: ({ row }) => formatDateTime(row.original.posted_at),
      },
      {
        id: "posted_by",
        enableSorting: false,
        header: () => translate("inventory.adjustments.postedBy"),
        cell: ({ row }) =>
          displayName(
            row.original.posted_by_name,
            row.original.posted_by_email,
          ),
      },
      {
        accessorKey: "line_count",
        header: () => translate("inventory.adjustments.lines"),
      },
      {
        id: "note",
        enableSorting: false,
        header: () => translate("common.note"),
        cell: ({ row }) => (
          <span className="text-muted-foreground">
            {row.original.note ?? ""}
          </span>
        ),
      },
      {
        id: "status",
        enableSorting: false,
        header: () => translate("common.status"),
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
              aria-label={translate("inventory.adjustments.view", {
                number: row.original.number,
              })}
              onClick={() => setViewingId(row.original.id)}
            >
              <Eye />
            </Button>
            {canReverse && row.original.status === "posted" && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setReversing(row.original)}
              >
                <Undo2 className="mr-1" />
                {translate("inventory.adjustments.reverse")}
              </Button>
            )}
          </div>
        ),
      },
    ],
    [canReverse, formatDateTime],
  )

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            {t("inventory.adjustments.title")}
          </h1>
          <p className="text-muted-foreground">
            {t("inventory.adjustments.description")}
          </p>
        </div>
        {canAdjust && <NewAdjustmentDialog />}
      </div>

      <Select
        value={status ?? ALL}
        onValueChange={(value) =>
          setStatus(value === ALL ? undefined : (value as AdjustmentStatus))
        }
      >
        <SelectTrigger
          className="w-44"
          aria-label={t("inventory.statusFilter")}
        >
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>{t("inventory.allStatuses")}</SelectItem>
          <SelectItem value="posted">
            {t("inventory.adjustments.posted")}
          </SelectItem>
          <SelectItem value="reversed">
            {t("inventory.adjustments.reversed")}
          </SelectItem>
        </SelectContent>
      </Select>

      {isPending ? (
        <Skeleton className="h-40 w-full" />
      ) : (
        <DataTable columns={columns} data={data?.data ?? []} />
      )}

      <AdjustmentDetail
        adjustmentId={viewingId}
        onClose={() => setViewingId(undefined)}
      />
      <ConfirmDialog
        open={reversing !== undefined}
        onOpenChange={(open) => !open && closeReverse()}
        title={t("inventory.adjustments.reverseTitle", {
          number: reversing?.number ?? "",
        })}
        description={t("inventory.adjustments.reverseDescription")}
        confirmLabel={t("inventory.adjustments.reverse")}
        destructive
        loading={reverse.isPending}
        onConfirm={() => reversing && reverse.mutate(reversing)}
      >
        <div className="grid gap-1.5">
          <Label htmlFor="reversal-note">
            {t("inventory.adjustments.reason")}
          </Label>
          <Input
            id="reversal-note"
            maxLength={500}
            value={reversalNote}
            onChange={(e) => setReversalNote(e.target.value)}
          />
        </div>
      </ConfirmDialog>
    </div>
  )
}
