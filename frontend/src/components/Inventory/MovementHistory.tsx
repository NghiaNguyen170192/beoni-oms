import { useQuery } from "@tanstack/react-query"
import { useState } from "react"

import type { InventoryItemPublic, MovementType } from "@/client"
import { Badge } from "@/components/ui/badge"
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
import { useFormatters } from "@/hooks/useBusinessSettings"
import { useI18n } from "@/i18n"
import { formatNumber } from "@/lib/format"
import { MOVEMENT_TYPE_LABELS, UNIT_LABELS } from "@/lib/labels"
import { displayName } from "@/lib/permissions"
import { movementsQueryOptions } from "./queries"

const ALL = "all"

interface MovementHistoryProps {
  item: InventoryItemPublic | undefined
  onClose: () => void
}

export function MovementHistory({ item, onClose }: MovementHistoryProps) {
  return (
    <Sheet
      open={item !== undefined}
      onOpenChange={(open) => !open && onClose()}
    >
      <SheetContent className="w-full sm:max-w-3xl overflow-y-auto">
        {item && <MovementHistoryContent item={item} />}
      </SheetContent>
    </Sheet>
  )
}

function MovementHistoryContent({ item }: { item: InventoryItemPublic }) {
  const { t } = useI18n()
  const { formatMoney, formatUnitCost, formatDateTime } = useFormatters()
  const [movementType, setMovementType] = useState<MovementType>()
  const { data, isPending } = useQuery(
    movementsQueryOptions(item.id, movementType),
  )

  return (
    <>
      <SheetHeader>
        <SheetTitle>
          {item.sku} · {item.name}
        </SheetTitle>
        <SheetDescription>
          {t("inventory.movements.summary", {
            quantity: formatNumber(item.quantity),
            unit: t(UNIT_LABELS[item.base_unit]),
            cost: formatUnitCost(item.avg_unit_cost),
          })}
        </SheetDescription>
      </SheetHeader>
      <div className="flex flex-col gap-4 px-4 pb-6">
        <Select
          value={movementType ?? ALL}
          onValueChange={(value) =>
            setMovementType(value === ALL ? undefined : (value as MovementType))
          }
        >
          <SelectTrigger
            className="w-48"
            aria-label={t("inventory.movements.typeFilter")}
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>{t("inventory.movements.all")}</SelectItem>
            {(Object.keys(MOVEMENT_TYPE_LABELS) as MovementType[]).map(
              (value) => (
                <SelectItem key={value} value={value}>
                  {t(MOVEMENT_TYPE_LABELS[value])}
                </SelectItem>
              ),
            )}
          </SelectContent>
        </Select>

        {isPending ? (
          <Skeleton className="h-32 w-full" />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("inventory.movements.time")}</TableHead>
                <TableHead>{t("inventory.movements.type")}</TableHead>
                <TableHead className="text-right">
                  {t("inventory.movements.change")}
                </TableHead>
                <TableHead className="text-right">
                  {t("inventory.movements.unitCost")}
                </TableHead>
                <TableHead className="text-right">
                  {t("inventory.field.value")}
                </TableHead>
                <TableHead className="text-right">
                  {t("inventory.movements.balance")}
                </TableHead>
                <TableHead>{t("inventory.movements.by")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.data.length ? (
                data.data.map((movement) => (
                  <TableRow key={movement.id}>
                    <TableCell className="whitespace-nowrap">
                      {formatDateTime(movement.occurred_at)}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        {t(MOVEMENT_TYPE_LABELS[movement.movement_type])}
                        {movement.cost_uncertain && (
                          <Badge
                            variant="outline"
                            title={t("inventory.movements.costUncertain")}
                          >
                            ?
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {Number(movement.quantity) > 0 ? "+" : ""}
                      {formatNumber(movement.quantity)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatUnitCost(movement.unit_cost)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatMoney(movement.value)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatNumber(movement.quantity_after)}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {displayName(movement.actor_name, movement.actor_email)}
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell
                    colSpan={7}
                    className="h-24 text-center text-muted-foreground"
                  >
                    {t("inventory.movements.empty")}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        )}
      </div>
    </>
  )
}
