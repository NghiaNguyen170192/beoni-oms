import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"

import { ReportsService } from "@/client"
import { reportFilename } from "@/components/Reports/download"
import { ExportButton } from "@/components/Reports/ExportButton"
import { PeriodFilter, useReportRange } from "@/components/Reports/PeriodFilter"
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
import { t as translate, useI18n } from "@/i18n"
import { formatNumber } from "@/lib/format"
import { requirePermission } from "@/lib/permissions"

export const Route = createFileRoute("/_layout/reports/inventory")({
  component: InventoryReports,
  beforeLoad: requirePermission("reports:inventory"),
  head: () => ({
    meta: [{ title: translate("reports.inventoryTitle") }],
  }),
})

function InventoryReports() {
  const { t } = useI18n()
  const { formatMoney } = useFormatters()
  const range = useReportRange()
  const movements = useQuery({
    queryKey: ["inventory-movements", range.dateFrom, range.dateTo],
    queryFn: () =>
      ReportsService.readMovements({
        dateFrom: range.dateFrom,
        dateTo: range.dateTo,
      }),
    enabled: range.ready,
  })
  const status = useQuery({
    queryKey: ["stock-status"],
    queryFn: () => ReportsService.readStockStatus(),
  })

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            {t("reports.inventoryTitle")}
          </h1>
          <p className="text-sm text-muted-foreground">
            {t("reports.inventoryDescription")}
          </p>
        </div>
        {range.ready ? (
          <ExportButton
            testId="export-movements"
            label={t("reports.exportMovements")}
            filename={reportFilename(
              "inventory-movements",
              range.dateFrom,
              range.dateTo,
            )}
            load={() =>
              ReportsService.exportMovements({
                dateFrom: range.dateFrom,
                dateTo: range.dateTo,
              })
            }
          />
        ) : null}
      </div>
      <PeriodFilter
        dateFrom={range.dateFrom}
        dateTo={range.dateTo}
        onChange={range.setRange}
      />
      {status.data ? (
        <div className="flex flex-wrap gap-3">
          <div className="rounded-md border px-3 py-2">
            <div className="text-xs text-muted-foreground">
              {t("reports.stockValue")}
            </div>
            <div
              className="text-lg font-semibold tabular-nums"
              data-testid="stock-value"
              data-value={status.data.total_value}
            >
              {formatMoney(status.data.total_value)}
            </div>
          </div>
          <div className="rounded-md border px-3 py-2">
            <div className="text-xs text-muted-foreground">
              {t("reports.lowStock")}
            </div>
            <div className="text-lg font-semibold tabular-nums">
              {status.data.low_stock.length}
            </div>
          </div>
          <div className="rounded-md border px-3 py-2">
            <div className="text-xs text-muted-foreground">
              {t("reports.negativeStock")}
            </div>
            <div className="text-lg font-semibold tabular-nums">
              {status.data.negative_stock.length}
            </div>
          </div>
        </div>
      ) : null}
      {movements.data ? (
        <div className="overflow-x-auto">
          <p
            className="sr-only"
            data-testid="movement-count"
            data-count={movements.data.count}
          />
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("reports.sku")}</TableHead>
                <TableHead>{t("common.name")}</TableHead>
                <TableHead className="text-right">
                  {t("reports.opening")}
                </TableHead>
                <TableHead className="text-right">
                  {t("reports.received")}
                </TableHead>
                <TableHead className="text-right">
                  {t("reports.consumed")}
                </TableHead>
                <TableHead className="text-right">
                  {t("reports.adjustments")}
                </TableHead>
                <TableHead className="text-right">
                  {t("reports.spoilage")}
                </TableHead>
                <TableHead className="text-right">
                  {t("reports.returns")}
                </TableHead>
                <TableHead className="text-right">
                  {t("reports.reversals")}
                </TableHead>
                <TableHead className="text-right">
                  {t("reports.closing")}
                </TableHead>
                <TableHead className="text-right">
                  {t("reports.closingValue")}
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {movements.data.data.map((row) => (
                <TableRow
                  key={row.item_id}
                  data-testid="movement-row"
                  data-closing={row.closing}
                >
                  <TableCell>{row.sku}</TableCell>
                  <TableCell>{row.name}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatNumber(row.opening)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatNumber(row.received)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatNumber(row.consumed)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatNumber(row.adjustments)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatNumber(row.spoilage)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatNumber(row.returns)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatNumber(row.reversals)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatNumber(row.closing)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatMoney(row.closing_value)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : (
        <Skeleton className="h-64" />
      )}
    </div>
  )
}
