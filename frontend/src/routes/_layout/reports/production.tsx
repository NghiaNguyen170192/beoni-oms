import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useState } from "react"

import { type ProductionBatchStatus, ReportsService } from "@/client"
import { reportFilename } from "@/components/Reports/download"
import { ExportButton } from "@/components/Reports/ExportButton"
import { PeriodFilter, useReportRange } from "@/components/Reports/PeriodFilter"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { type MessageKey, t as translate, useI18n } from "@/i18n"
import { formatNumber } from "@/lib/format"
import { requirePermission } from "@/lib/permissions"

const STATUSES: ProductionBatchStatus[] = [
  "draft",
  "completed",
  "cancelled",
  "reversed",
]
const STATUS_LABELS: Record<ProductionBatchStatus, MessageKey> = {
  draft: "production.status.draft",
  completed: "production.status.completed",
  cancelled: "production.status.cancelled",
  reversed: "production.status.reversed",
}

export const Route = createFileRoute("/_layout/reports/production")({
  component: ProductionReports,
  beforeLoad: requirePermission("reports:inventory"),
  head: () => ({
    meta: [{ title: translate("reports.productionReportTitle") }],
  }),
})

function ProductionReports() {
  const { t } = useI18n()
  const range = useReportRange()
  const [status, setStatus] = useState<ProductionBatchStatus | "">("")
  const [productId, setProductId] = useState("")
  const report = useQuery({
    queryKey: ["production-report", range.dateFrom, range.dateTo],
    queryFn: () =>
      ReportsService.readProductionReport({
        dateFrom: range.dateFrom,
        dateTo: range.dateTo,
      }),
    enabled: range.ready,
  })
  const products = [
    ...new Map(
      (report.data?.data ?? []).map((row) => [
        row.menu_item_id,
        { id: row.menu_item_id, name: row.menu_item_name },
      ]),
    ).values(),
  ]
  const rows = (report.data?.data ?? []).filter(
    (row) =>
      (!status || row.status === status) &&
      (!productId || row.menu_item_id === productId),
  )
  const dates = { dateFrom: range.dateFrom, dateTo: range.dateTo }
  const selectedStatus = status || undefined
  const selectedProductId = productId || undefined

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            {t("reports.productionReportTitle")}
          </h1>
          <p className="text-sm text-muted-foreground">
            {t("reports.productionReportDescription")}
          </p>
        </div>
        {range.ready ? (
          <ExportButton
            testId="export-production-report"
            label={t("reports.export")}
            filename={reportFilename(
              "production-report",
              range.dateFrom,
              range.dateTo,
            )}
            load={() =>
              ReportsService.exportProductionReport({
                ...dates,
                status: selectedStatus,
                menuItemId: selectedProductId,
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
      <div className="flex flex-wrap gap-3">
        <div className="grid gap-1.5">
          <Label htmlFor="production-report-status">
            {t("reports.status")}
          </Label>
          <select
            id="production-report-status"
            className="h-9 min-w-44 rounded-md border bg-transparent px-3 text-sm"
            value={status}
            onChange={(event) =>
              setStatus(event.target.value as ProductionBatchStatus | "")
            }
          >
            <option value="">{t("reports.allStatuses")}</option>
            {STATUSES.map((value) => (
              <option key={value} value={value}>
                {t(STATUS_LABELS[value])}
              </option>
            ))}
          </select>
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="production-report-product">
            {t("reports.product")}
          </Label>
          <select
            id="production-report-product"
            className="h-9 min-w-52 rounded-md border bg-transparent px-3 text-sm"
            value={productId}
            onChange={(event) => setProductId(event.target.value)}
          >
            <option value="">{t("reports.allProducts")}</option>
            {products.map((product) => (
              <option key={product.id} value={product.id}>
                {product.name}
              </option>
            ))}
          </select>
        </div>
      </div>
      {report.error ? (
        <p className="text-sm text-destructive" role="alert">
          {report.error instanceof Error
            ? report.error.message
            : t("reports.loadFailed")}
        </p>
      ) : null}
      {report.data ? (
        <div className="overflow-x-auto">
          <p
            className="sr-only"
            data-testid="production-report-count"
            data-count={rows.length}
          />
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("reports.period")}</TableHead>
                <TableHead>{t("production.batch.numberHeader")}</TableHead>
                <TableHead>{t("reports.status")}</TableHead>
                <TableHead>{t("reports.product")}</TableHead>
                <TableHead className="text-right">
                  {t("reports.plannedYield")}
                </TableHead>
                <TableHead className="text-right">
                  {t("reports.actualYield")}
                </TableHead>
                <TableHead className="text-right">
                  {t("reports.waste")}
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => (
                <TableRow key={`${row.batch_id}-${row.menu_item_id}`}>
                  <TableCell>{row.report_date}</TableCell>
                  <TableCell>
                    {t("production.batch.number", { number: row.batch_number })}
                  </TableCell>
                  <TableCell>{t(STATUS_LABELS[row.status])}</TableCell>
                  <TableCell>{row.menu_item_name}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatNumber(row.planned_quantity)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {row.actual_good_quantity == null
                      ? "—"
                      : formatNumber(row.actual_good_quantity)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatNumber(row.waste_quantity)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : report.isPending ? (
        <Skeleton className="h-64" />
      ) : null}
    </div>
  )
}
