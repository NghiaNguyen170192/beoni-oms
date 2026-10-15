import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"

import { ReportsService } from "@/client"
import { PeriodFilter, useReportRange } from "@/components/Reports/PeriodFilter"
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useFormatters } from "@/hooks/useBusinessSettings"
import { t as translate, useI18n } from "@/i18n"

export const Route = createFileRoute("/_layout/")({
  component: Dashboard,
  head: () => ({
    meta: [{ title: translate("nav.dashboard") }],
  }),
})

function Metric({
  label,
  value,
  testId,
  raw,
}: {
  label: string
  value: string
  testId: string
  raw: string
}) {
  return (
    <Card>
      <CardHeader>
        <CardDescription>{label}</CardDescription>
        <CardTitle
          className="text-2xl tabular-nums"
          data-testid={testId}
          data-value={raw}
        >
          {value}
        </CardTitle>
      </CardHeader>
    </Card>
  )
}

function Dashboard() {
  const { t } = useI18n()
  const { formatMoney } = useFormatters()
  const range = useReportRange()
  const dashboard = useQuery({
    queryKey: ["dashboard", range.dateFrom, range.dateTo],
    queryFn: () =>
      ReportsService.readDashboard({
        dateFrom: range.dateFrom,
        dateTo: range.dateTo,
      }),
    enabled: range.ready,
  })
  const data = dashboard.data
  const financial = data && "cogs" in data ? data : null

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold tracking-tight">
        {t("nav.dashboard")}
      </h1>
      <PeriodFilter
        dateFrom={range.dateFrom}
        dateTo={range.dateTo}
        onChange={range.setRange}
      />
      {dashboard.isLoading || !data ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Skeleton className="h-28" />
          <Skeleton className="h-28" />
          <Skeleton className="h-28" />
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Metric
            label={t("reports.netSales")}
            value={formatMoney(data.net_sales)}
            testId="dashboard-net-sales"
            raw={data.net_sales}
          />
          <Metric
            label={t("reports.orders")}
            value={String(data.order_count)}
            testId="dashboard-order-count"
            raw={String(data.order_count)}
          />
          <Metric
            label={t("reports.averageOrder")}
            value={formatMoney(data.average_order_value)}
            testId="dashboard-average-order"
            raw={data.average_order_value}
          />
          <Metric
            label={t("reports.discounts")}
            value={formatMoney(data.discounts)}
            testId="dashboard-discounts"
            raw={data.discounts}
          />
          <Metric
            label={t("reports.refunds")}
            value={formatMoney(data.refunds)}
            testId="dashboard-refunds"
            raw={data.refunds}
          />
          <Metric
            label={t("reports.lowStock")}
            value={String(data.low_stock_count)}
            testId="dashboard-low-stock"
            raw={String(data.low_stock_count)}
          />
          {financial ? (
            <>
              <Metric
                label={t("reports.cogs")}
                value={formatMoney(financial.cogs)}
                testId="dashboard-cogs"
                raw={financial.cogs}
              />
              <Metric
                label={t("reports.grossProfit")}
                value={formatMoney(financial.gross_profit)}
                testId="dashboard-gross-profit"
                raw={financial.gross_profit}
              />
              <Metric
                label={t("reports.expenses")}
                value={formatMoney(financial.expenses)}
                testId="dashboard-expenses"
                raw={financial.expenses}
              />
              <Metric
                label={t("reports.operatingProfit")}
                value={formatMoney(financial.operating_profit)}
                testId="dashboard-operating-profit"
                raw={financial.operating_profit}
              />
            </>
          ) : null}
        </div>
      )}
      {dashboard.isError ? (
        <p className="text-sm text-destructive">{t("common.error")}</p>
      ) : null}
    </div>
  )
}
