export const DEFAULT_CURRENCY = "VND"
export const DEFAULT_TIMEZONE = "Asia/Ho_Chi_Minh"

/** Display only: amounts arrive from the API as decimal strings and are never recomputed here. */
export function formatMoney(
  amount: string | number,
  currency: string = DEFAULT_CURRENCY,
): string {
  return new Intl.NumberFormat("vi-VN", { style: "currency", currency }).format(
    Number(amount),
  )
}

export function formatDateTime(
  value: string | Date,
  timeZone: string = DEFAULT_TIMEZONE,
): string {
  return new Intl.DateTimeFormat("vi-VN", {
    dateStyle: "short",
    timeStyle: "medium",
    timeZone,
  }).format(new Date(value))
}

/** Display only: quantity or unit-cost strings from the API, trailing zeros dropped. */
export function formatNumber(
  value: string | number,
  maximumFractionDigits = 4,
): string {
  return new Intl.NumberFormat("vi-VN", { maximumFractionDigits }).format(
    Number(value),
  )
}

/** Per-unit costs keep up to 4 decimals, which standard currency formatting rounds away. */
export function formatUnitCost(
  value: string | number,
  currency: string = DEFAULT_CURRENCY,
): string {
  return new Intl.NumberFormat("vi-VN", {
    style: "currency",
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 4,
  }).format(Number(value))
}
