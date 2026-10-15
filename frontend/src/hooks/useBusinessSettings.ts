import { useQuery } from "@tanstack/react-query"
import { useEffect } from "react"

import { SettingsService } from "@/client"
import { setLanguage } from "@/i18n"
import {
  DEFAULT_CURRENCY,
  DEFAULT_TIMEZONE,
  formatDateTime,
  formatMoney,
  formatUnitCost,
} from "@/lib/format"
import { isLoggedIn } from "./useAuth"

export const businessSettingsQueryKey = ["businessSettings"]

/** Business settings; also applies the business-wide interface language. */
export function useBusinessSettings() {
  const query = useQuery({
    queryKey: businessSettingsQueryKey,
    queryFn: () => SettingsService.readBusinessSettings(),
    enabled: isLoggedIn(),
    staleTime: 5 * 60 * 1000,
  })
  const language = query.data?.language
  useEffect(() => {
    if (language) setLanguage(language)
  }, [language])
  return query
}

/** Money and date formatters bound to the business currency and timezone. */
export function useFormatters() {
  const { data: settings } = useBusinessSettings()
  const currency = settings?.currency_code ?? DEFAULT_CURRENCY
  const timeZone = settings?.timezone ?? DEFAULT_TIMEZONE

  return {
    currency,
    timeZone,
    formatMoney: (amount: string | number) => formatMoney(amount, currency),
    formatUnitCost: (value: string | number) => formatUnitCost(value, currency),
    formatDateTime: (value: string | Date) => formatDateTime(value, timeZone),
  }
}
