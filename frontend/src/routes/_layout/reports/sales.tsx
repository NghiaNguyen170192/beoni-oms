import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { lazy, Suspense, useState } from "react"

import { ReportsService } from "@/client"
import { reportFilename } from "@/components/Reports/download"
import { ExportButton } from "@/components/Reports/ExportButton"
import { PeriodFilter, useReportRange } from "@/components/Reports/PeriodFilter"
import { Badge } from "@/components/ui/badge"
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
import { useFormatters } from "@/hooks/useBusinessSettings"
import { t as translate, useI18n } from "@/i18n"
import { formatNumber } from "@/lib/format"
import { requirePermission } from "@/lib/permissions"

const SalesChart = lazy(() =>
  import("@/components/Reports/SalesChart").then((module) => ({
    default: module.SalesChart,
  })),
)

export const Route = createFileRoute("/_layout/reports/sales")({
  component: SalesReports,
  beforeLoad: requirePermission("reports:sales"),
  head: () => ({
    meta: [{ title: translate("reports.salesTitle") }],
  }),
})

function SalesReports() {
  const { t } = useI18n()
  const { formatMoney } = useFormatters()
  const range = useReportRange()
  const [groupBy, setGroupBy] = useState<"day" | "week" | "month">("day")
  const summary = useQuery({
    queryKey: ["sales-summary", range.dateFrom, range.dateTo, groupBy],
    queryFn: () =>
      ReportsService.readSalesSummary({
        dateFrom: range.dateFrom,
        dateTo: range.dateTo,
        groupBy,
      }),
    enabled: range.ready,
  })
  const products = useQuery({
    queryKey: ["sales-products", range.dateFrom, range.dateTo],
    queryFn: () =>
      ReportsService.readProducts({
        dateFrom: range.dateFrom,
        dateTo: range.dateTo,
      }),
    enabled: range.ready,
  })
  const filename = (name: string) =>
    reportFilename(name, range.dateFrom, range.dateTo)

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          {t("reports.salesTitle")}
        </h1>
        <p className="text-sm text-muted-foreground">
          {t("reports.salesDescription")}
        </p>
      </div>
      <PeriodFilter
        dateFrom={range.dateFrom}
        dateTo={range.dateTo}
        onChange={range.setRange}
      />
      <div className="grid gap-1.5">
        <Label htmlFor="group-by">{t("reports.groupBy")}</Label>
        <select
          id="group-by"
          className="h-9 w-40 rounded-md border bg-transparent px-3 text-sm"
          value={groupBy}
          onChange={(event) =>
            setGroupBy(event.target.value as "day" | "week" | "month")
          }
        >
          <option value="day">{t("reports.group.day")}</option>
          <option value="week">{t("reports.group.week")}</option>
          <option value="month">{t("reports.group.month")}</option>
        </select>
      </div>
      {summary.data ? (
        <>
          <div className="flex flex-wrap items-end justify-between gap-3">
            <p
              className="text-2xl font-semibold tabular-nums"
              data-testid="sales-net"
              data-value={summary.data.net_sales}
              data-count={summary.data.data.length}
            >
              {formatMoney(summary.data.net_sales)}
            </p>
            <ExportButton
              testId="export-sales-summary"
              label={t("reports.exportSummary")}
              filename={filename("sales-summary")}
              load={() =>
                ReportsService.exportSalesSummary({
                  dateFrom: range.dateFrom,
                  dateTo: range.dateTo,
                  groupBy,
                })
              }
            />
          </div>
          <Suspense fallback={<Skeleton className="h-64" />}>
            <SalesChart
              points={summary.data.data.map((row) => ({
                period: row.period_start,
                net: Number(row.net_sales),
              }))}
            />
          </Suspense>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("reports.period")}</TableHead>
                  <TableHead className="text-right">
                    {t("reports.grossSales")}
                  </TableHead>
                  <TableHead className="text-right">
                    {t("reports.discounts")}
                  </TableHead>
                  <TableHead className="text-right">
                    {t("reports.refunds")}
                  </TableHead>
                  <TableHead className="text-right">
                    {t("reports.netSales")}
                  </TableHead>
                  <TableHead className="text-right">
                    {t("reports.orders")}
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {summary.data.data.map((row) => (
                  <TableRow key={row.period_start}>
                    <TableCell>{row.period_start}</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatMoney(row.gross_sales)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatMoney(row.discounts)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatMoney(row.refunds)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatMoney(row.net_sales)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {row.order_count}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <h2 className="text-lg font-semibold">{t("reports.payments")}</h2>
          <div className="flex flex-wrap gap-3">
            {summary.data.payments.map((row) => (
              <div key={row.method_id} className="rounded-md border px-3 py-2">
                <div className="text-xs text-muted-foreground">
                  {row.method_name}
                </div>
                <div className="text-lg font-semibold tabular-nums">
                  {formatMoney(row.amount)}
                </div>
              </div>
            ))}
          </div>
        </>
      ) : (
        <Skeleton className="h-64" />
      )}
      {products.data ? (
        <>
          <div className="flex flex-wrap items-end justify-between gap-3">
            <h2 className="text-lg font-semibold">{t("reports.products")}</h2>
            <ExportButton
              testId="export-products"
              label={t("reports.exportProducts")}
              filename={filename("product-performance")}
              load={() =>
                ReportsService.exportProducts({
                  dateFrom: range.dateFrom,
                  dateTo: range.dateTo,
                })
              }
            />
          </div>
          <p
            className="sr-only"
            data-testid="product-net"
            data-value={products.data.net_sales}
            data-count={products.data.data.length}
          >
            {products.data.net_sales}
          </p>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("common.name")}</TableHead>
                  <TableHead className="text-right">
                    {t("reports.quantity")}
                  </TableHead>
                  <TableHead className="text-right">
                    {t("reports.netSales")}
                  </TableHead>
                  <TableHead className="text-right">
                    {t("reports.share")}
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {products.data.data.map((row) => (
                  <TableRow key={row.menu_item_id}>
                    <TableCell>
                      {row.name}
                      {row.best_seller ? (
                        <Badge className="ml-2" variant="secondary">
                          {t("reports.bestSeller")}
                        </Badge>
                      ) : null}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatNumber(row.quantity)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatMoney(row.net_sales)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatNumber(row.share, 1)}%
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </>
      ) : null}
    </div>
  )
}
