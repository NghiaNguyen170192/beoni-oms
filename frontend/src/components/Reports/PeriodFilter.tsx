import { useEffect, useState } from "react"

import { ReportsService } from "@/client"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useI18n } from "@/i18n"

const PRESETS = [
  "today",
  "yesterday",
  "last_7_days",
  "this_month",
  "last_month",
] as const

type Preset = (typeof PRESETS)[number]

export function useReportRange() {
  const [dateFrom, setDateFrom] = useState("")
  const [dateTo, setDateTo] = useState("")

  useEffect(() => {
    let cancelled = false
    void ReportsService.readPreset({ preset: "today" }).then((period) => {
      if (!cancelled) {
        setDateFrom(period.date_from)
        setDateTo(period.date_to)
      }
    })
    return () => {
      cancelled = true
    }
  }, [])

  return {
    dateFrom,
    dateTo,
    setRange: (from: string, to: string) => {
      setDateFrom(from)
      setDateTo(to)
    },
    ready: Boolean(dateFrom && dateTo),
  }
}

export function PeriodFilter({
  dateFrom,
  dateTo,
  onChange,
}: {
  dateFrom: string
  dateTo: string
  onChange: (dateFrom: string, dateTo: string) => void
}) {
  const { t } = useI18n()

  const applyPreset = (preset: Preset) => {
    void ReportsService.readPreset({ preset }).then((period) => {
      onChange(period.date_from, period.date_to)
    })
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-2">
        {PRESETS.map((preset) => (
          <Button
            key={preset}
            type="button"
            variant="outline"
            size="sm"
            data-testid={`preset-${preset}`}
            onClick={() => applyPreset(preset)}
          >
            {t(`reports.presets.${preset}`)}
          </Button>
        ))}
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <div className="grid gap-1.5">
          <Label htmlFor="report-from">{t("reports.from")}</Label>
          <Input
            id="report-from"
            type="date"
            value={dateFrom}
            onChange={(event) => onChange(event.target.value, dateTo)}
          />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="report-to">{t("reports.to")}</Label>
          <Input
            id="report-to"
            type="date"
            value={dateTo}
            onChange={(event) => onChange(dateFrom, event.target.value)}
          />
        </div>
      </div>
    </div>
  )
}
