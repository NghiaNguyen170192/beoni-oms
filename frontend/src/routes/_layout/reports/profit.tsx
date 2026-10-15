import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"

import { AccountingService, ReportsService } from "@/client"
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
import useAuth from "@/hooks/useAuth"
import { useFormatters } from "@/hooks/useBusinessSettings"
import { type MessageKey, t as translate, useI18n } from "@/i18n"
import { hasPermission, requirePermission } from "@/lib/permissions"

const LINE_LABELS: Record<string, MessageKey> = {
  net_sales: "reports.netSales",
  cogs: "reports.cogs",
  gross_profit: "reports.grossProfit",
  expenses: "reports.expenses",
  operating_profit: "reports.operatingProfit",
}

export const Route = createFileRoute("/_layout/reports/profit")({
  component: ProfitReports,
  beforeLoad: requirePermission("reports:financial"),
  head: () => ({
    meta: [{ title: translate("reports.profitTitle") }],
  }),
})

function ProfitReports() {
  const { t } = useI18n()
  const { user } = useAuth()
  const canIncome = hasPermission(user, "finance:view")
  const { formatMoney } = useFormatters()
  const range = useReportRange()
  const enabled = range.ready
  const dates = { dateFrom: range.dateFrom, dateTo: range.dateTo }
  const statement = useQuery({
    queryKey: ["profit-statement", range.dateFrom, range.dateTo],
    queryFn: () => ReportsService.readStatement(dates),
    enabled,
  })
  const comparison = useQuery({
    queryKey: ["profit-comparison", range.dateFrom, range.dateTo],
    queryFn: () => ReportsService.readComparison(dates),
    enabled,
  })
  const expenses = useQuery({
    queryKey: ["expense-breakdown", range.dateFrom, range.dateTo],
    queryFn: () => ReportsService.readExpenses(dates),
    enabled,
  })
  const income = useQuery({
    queryKey: ["income-listing", range.dateFrom, range.dateTo],
    queryFn: () => AccountingService.readIncome(dates),
    enabled: enabled && canIncome,
  })
  const filename = (name: string) =>
    reportFilename(name, range.dateFrom, range.dateTo)

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          {t("reports.profitTitle")}
        </h1>
        <p className="text-sm text-muted-foreground">{t("reports.estimate")}</p>
      </div>
      <PeriodFilter
        dateFrom={range.dateFrom}
        dateTo={range.dateTo}
        onChange={range.setRange}
      />
      {statement.data ? (
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-muted-foreground">
              {statement.data.note}
            </p>
            <ExportButton
              testId="export-statement"
              label={t("reports.exportStatement")}
              filename={filename("profit-statement")}
              load={() => ReportsService.exportStatement(dates)}
            />
          </div>
          <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <div>
              <dt className="text-xs text-muted-foreground">
                {t("reports.netSales")}
              </dt>
              <dd
                className="text-lg font-semibold tabular-nums"
                data-testid="profit-net"
                data-value={statement.data.net_sales}
              >
                {formatMoney(statement.data.net_sales)}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">
                {t("reports.cogs")}
              </dt>
              <dd className="text-lg font-semibold tabular-nums">
                {formatMoney(statement.data.cogs)}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">
                {t("reports.grossProfit")}
              </dt>
              <dd className="text-lg font-semibold tabular-nums">
                {formatMoney(statement.data.gross_profit)}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">
                {t("reports.grossMargin")}
              </dt>
              <dd className="text-lg font-semibold tabular-nums">
                {statement.data.gross_margin}%
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">
                {t("reports.expenses")}
              </dt>
              <dd className="text-lg font-semibold tabular-nums">
                {formatMoney(statement.data.expenses)}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">
                {t("reports.operatingProfit")}
              </dt>
              <dd
                className="text-lg font-semibold tabular-nums"
                data-testid="profit-operating"
                data-value={statement.data.operating_profit}
              >
                {formatMoney(statement.data.operating_profit)}
              </dd>
            </div>
          </dl>
          {statement.data.uncertain_cost_lines > 0 ? (
            <p className="text-sm text-muted-foreground">
              {t("reports.uncertainCosts")}:{" "}
              {statement.data.uncertain_cost_lines}
            </p>
          ) : null}
          {statement.data.missing_cost_lines > 0 ? (
            <p className="text-sm text-muted-foreground">
              {t("reports.missingCosts")}: {statement.data.missing_cost_lines}
            </p>
          ) : null}
        </div>
      ) : (
        <Skeleton className="h-40" />
      )}
      {comparison.data ? (
        <div className="flex flex-col gap-3">
          <h2 className="text-lg font-semibold">{t("reports.comparison")}</h2>
          <p className="text-sm text-muted-foreground">
            {comparison.data.compare_from} – {comparison.data.compare_to}
          </p>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead />
                <TableHead className="text-right">
                  {t("reports.current")}
                </TableHead>
                <TableHead className="text-right">
                  {t("reports.previous")}
                </TableHead>
                <TableHead className="text-right">
                  {t("reports.change")}
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {comparison.data.lines.map((line) => (
                <TableRow key={line.key}>
                  <TableCell>
                    {LINE_LABELS[line.key]
                      ? t(LINE_LABELS[line.key])
                      : line.key}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatMoney(line.current)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatMoney(line.previous)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatMoney(line.change)}
                    {line.change_percent != null
                      ? ` (${line.change_percent}%)`
                      : ""}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : null}
      {expenses.data ? (
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <h2 className="text-lg font-semibold">
              {t("reports.expenseBreakdown")}
            </h2>
            <ExportButton
              testId="export-expenses"
              label={t("reports.exportExpenses")}
              filename={filename("expense-breakdown")}
              load={() => ReportsService.exportExpenses(dates)}
            />
          </div>
          <p
            className="text-sm tabular-nums"
            data-testid="expense-total"
            data-value={expenses.data.total}
            data-count={expenses.data.data.length}
          >
            {formatMoney(expenses.data.total)}
          </p>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("reports.category")}</TableHead>
                <TableHead className="text-right">
                  {t("reports.amount")}
                </TableHead>
                <TableHead className="text-right">
                  {t("reports.share")}
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {expenses.data.data.map((row) => (
                <TableRow key={row.category_id}>
                  <TableCell>{row.category_name}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatMoney(row.amount)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {row.share}%
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : null}
      {income.data ? (
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <h2 className="text-lg font-semibold">{t("reports.income")}</h2>
            <ExportButton
              testId="export-income"
              label={t("reports.exportIncome")}
              filename={filename("income")}
              load={() => ReportsService.exportIncome(dates)}
            />
          </div>
          <p
            className="sr-only"
            data-testid="income-count"
            data-count={income.data.count}
          />
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("reports.order")}</TableHead>
                  <TableHead className="text-right">
                    {t("reports.netSales")}
                  </TableHead>
                  <TableHead className="text-right">
                    {t("reports.tax")}
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {income.data.data.map((row) => (
                  <TableRow
                    key={row.order_id}
                    data-testid="income-row"
                    data-net={row.net_sales}
                  >
                    <TableCell>{row.number}</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatMoney(row.net_sales)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatMoney(row.tax)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
      ) : null}
    </div>
  )
}
