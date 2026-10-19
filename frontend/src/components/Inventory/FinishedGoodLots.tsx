import { useQuery } from "@tanstack/react-query"

import type { InventoryItemPublic } from "@/client"
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
import { UNIT_LABELS } from "@/lib/labels"
import { finishedGoodLotsQueryOptions } from "./queries"

interface FinishedGoodLotsProps {
  item: InventoryItemPublic | undefined
  onClose: () => void
}

export function FinishedGoodLots({ item, onClose }: FinishedGoodLotsProps) {
  return (
    <Sheet
      open={item !== undefined}
      onOpenChange={(open) => !open && onClose()}
    >
      <SheetContent className="w-full overflow-y-auto sm:max-w-4xl">
        {item && <FinishedGoodLotsContent item={item} />}
      </SheetContent>
    </Sheet>
  )
}

function FinishedGoodLotsContent({ item }: { item: InventoryItemPublic }) {
  const { t } = useI18n()
  const { formatDateTime, formatUnitCost } = useFormatters()
  const { data, isPending, isError, error } = useQuery(
    finishedGoodLotsQueryOptions(item.id),
  )

  return (
    <>
      <SheetHeader>
        <SheetTitle>
          {t("inventory.lots.title")} · {item.name}
        </SheetTitle>
        <SheetDescription>
          {t("inventory.lots.description", {
            quantity: formatNumber(item.quantity),
            unit: t(UNIT_LABELS[item.base_unit]),
          })}
        </SheetDescription>
      </SheetHeader>
      <div className="px-4 pb-6">
        {isPending ? (
          <Skeleton className="h-32 w-full" />
        ) : isError ? (
          <p role="alert" className="text-destructive">
            {error instanceof Error ? error.message : t("common.error")}
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("inventory.lots.number")}</TableHead>
                <TableHead>{t("inventory.lots.source")}</TableHead>
                <TableHead>{t("inventory.lots.finishedAt")}</TableHead>
                <TableHead>{t("inventory.lots.expiry")}</TableHead>
                <TableHead className="text-right">
                  {t("inventory.lots.produced")}
                </TableHead>
                <TableHead className="text-right">
                  {t("inventory.lots.available")}
                </TableHead>
                <TableHead className="text-right">
                  {t("inventory.lots.unitCost")}
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.data.length ? (
                data.data.map((lot) => (
                  <TableRow key={lot.id}>
                    <TableCell className="font-medium">
                      {lot.lot_number}
                    </TableCell>
                    <TableCell>
                      {lot.batch_number
                        ? t("inventory.lots.batch", {
                            number: lot.batch_number,
                          })
                        : t("inventory.lots.openingStock")}
                    </TableCell>
                    <TableCell className="whitespace-nowrap">
                      {formatDateTime(lot.finished_at)}
                    </TableCell>
                    <TableCell>{lot.expiry_date ?? "—"}</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatNumber(lot.produced_quantity)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatNumber(lot.available_quantity)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {lot.unit_cost === null
                        ? "—"
                        : formatUnitCost(lot.unit_cost)}
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell
                    colSpan={7}
                    className="h-24 text-center text-muted-foreground"
                  >
                    {t("inventory.lots.empty")}
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
