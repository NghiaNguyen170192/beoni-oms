import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { type FormEvent, useState } from "react"

import { type PaymentStatus, PaymentsService, ReportsService } from "@/client"
import { reportFilename } from "@/components/Reports/download"
import { ExportButton } from "@/components/Reports/ExportButton"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useFormatters } from "@/hooks/useBusinessSettings"
import { t as translate, useI18n } from "@/i18n"
import { requirePermission } from "@/lib/permissions"

export const Route = createFileRoute("/_layout/payments")({
  component: PaymentsPage,
  beforeLoad: requirePermission("payments:read"),
  head: () => ({
    meta: [{ title: translate("payments.pageTitle") }],
  }),
})

function PaymentsPage() {
  const { t } = useI18n()
  const { formatMoney, formatDateTime } = useFormatters()
  const [dateFrom, setDateFrom] = useState("")
  const [dateTo, setDateTo] = useState("")
  const [status, setStatus] = useState<PaymentStatus | "">("")
  const [applied, setApplied] = useState({
    dateFrom: "",
    dateTo: "",
    status: "" as PaymentStatus | "",
  })

  const payments = useQuery({
    queryKey: ["payments", applied],
    queryFn: () =>
      PaymentsService.readPayments({
        dateFrom: applied.dateFrom || undefined,
        dateTo: applied.dateTo || undefined,
        status: applied.status || undefined,
        limit: 200,
      }),
  })
  const refunds = useQuery({
    queryKey: ["refunds", applied.dateFrom, applied.dateTo],
    queryFn: () =>
      PaymentsService.readRefunds({
        dateFrom: applied.dateFrom || undefined,
        dateTo: applied.dateTo || undefined,
        limit: 200,
      }),
  })

  const apply = (event: FormEvent) => {
    event.preventDefault()
    setApplied({ dateFrom, dateTo, status })
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          {t("payments.title")}
        </h1>
        <p className="text-sm text-muted-foreground">{t("payments.netHint")}</p>
      </div>
      <form className="flex flex-wrap items-end gap-3" onSubmit={apply}>
        <div className="grid gap-1.5">
          <Label htmlFor="pay-from">{t("payments.from")}</Label>
          <Input
            id="pay-from"
            type="date"
            value={dateFrom}
            onChange={(event) => setDateFrom(event.target.value)}
          />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="pay-to">{t("payments.to")}</Label>
          <Input
            id="pay-to"
            type="date"
            value={dateTo}
            onChange={(event) => setDateTo(event.target.value)}
          />
        </div>
        <Button type="submit" data-testid="payments-filter">
          {t("payments.filter")}
        </Button>
        {applied.dateFrom && applied.dateTo ? (
          <ExportButton
            testId="export-payments"
            label={t("reports.export")}
            filename={reportFilename(
              "payments",
              applied.dateFrom,
              applied.dateTo,
            )}
            load={() =>
              ReportsService.exportPayments({
                dateFrom: applied.dateFrom,
                dateTo: applied.dateTo,
                status: applied.status || undefined,
              })
            }
          />
        ) : null}
      </form>
      <p
        className="sr-only"
        data-testid="payments-count"
        data-count={payments.data?.count ?? 0}
      />
      <div className="flex flex-wrap gap-3">
        {payments.data?.totals.map((row) => (
          <div key={row.method_id} className="rounded-md border px-3 py-2">
            <div className="text-xs text-muted-foreground">
              {row.method_name}
            </div>
            <div className="text-lg font-semibold tabular-nums">
              {formatMoney(row.total)}
            </div>
          </div>
        ))}
      </div>
      <Tabs defaultValue="payments">
        <TabsList>
          <TabsTrigger value="payments">
            {t("payments.tabPayments")}
          </TabsTrigger>
          <TabsTrigger value="refunds">{t("payments.tabRefunds")}</TabsTrigger>
        </TabsList>
        <TabsContent value="payments">
          <div className="mb-3 flex gap-2">
            <Button
              type="button"
              variant={status === "" ? "default" : "outline"}
              onClick={() => {
                setStatus("")
                setApplied((current) => ({ ...current, status: "" }))
              }}
            >
              {t("common.all")}
            </Button>
            <Button
              type="button"
              variant={status === "active" ? "default" : "outline"}
              onClick={() => {
                setStatus("active")
                setApplied((current) => ({ ...current, status: "active" }))
              }}
            >
              {t("payments.status.active")}
            </Button>
            <Button
              type="button"
              variant={status === "voided" ? "default" : "outline"}
              onClick={() => {
                setStatus("voided")
                setApplied((current) => ({ ...current, status: "voided" }))
              }}
            >
              {t("payments.status.voided")}
            </Button>
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("payments.when")}</TableHead>
                <TableHead>{t("payments.order")}</TableHead>
                <TableHead>{t("payments.method")}</TableHead>
                <TableHead className="text-right">
                  {t("payments.amount")}
                </TableHead>
                <TableHead className="text-right">
                  {t("payments.change")}
                </TableHead>
                <TableHead>{t("payments.status")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {payments.data?.data.map((row) => (
                <TableRow key={row.id} data-amount={row.amount}>
                  <TableCell>{formatDateTime(row.recorded_at)}</TableCell>
                  <TableCell>{row.order_number}</TableCell>
                  <TableCell>{row.method_name}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatMoney(row.amount)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {row.change_amount ? formatMoney(row.change_amount) : "—"}
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={
                        row.status === "voided" ? "outline" : "secondary"
                      }
                    >
                      {t(
                        row.status === "voided"
                          ? "payments.status.voided"
                          : "payments.status.active",
                      )}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
              {payments.data?.data.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6}>{t("common.noResults")}</TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TabsContent>
        <TabsContent value="refunds">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("payments.when")}</TableHead>
                <TableHead>{t("payments.order")}</TableHead>
                <TableHead>{t("payments.method")}</TableHead>
                <TableHead className="text-right">
                  {t("payments.amount")}
                </TableHead>
                <TableHead>{t("payments.reason")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {refunds.data?.data.map((row) => (
                <TableRow key={row.id}>
                  <TableCell>{formatDateTime(row.recorded_at)}</TableCell>
                  <TableCell>{row.order_number}</TableCell>
                  <TableCell>{row.method_name}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatMoney(row.amount)}
                  </TableCell>
                  <TableCell>{row.reason}</TableCell>
                </TableRow>
              ))}
              {refunds.data?.data.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5}>{t("common.noResults")}</TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TabsContent>
      </Tabs>
    </div>
  )
}
