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

/**
 * Editable amounts: group the integer part with "." and keep up to
 * `maximumFractionDigits` decimals after a ",". The form keeps the canonical API
 * form ("29000.50") either way.
 */
export function formatAmountInput(
  value: string,
  maximumFractionDigits = 2,
): string {
  const negative = value.startsWith("-")
  const [whole = "", fraction] = (negative ? value.slice(1) : value).split(".")
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ".")
  const body = fraction
    ? `${grouped},${fraction.slice(0, maximumFractionDigits)}`
    : grouped
  return negative ? `-${body}` : body
}

/** Inverse of {@link formatAmountInput}: drop grouping, keep the decimal tail. */
export function parseAmountInput(
  value: string,
  maximumFractionDigits = 2,
): string {
  const negative = value.trim().startsWith("-")
  const [whole = "", fraction = ""] = value.replace(/[^\d,]/g, "").split(",")
  const trimmed = whole.replace(/^0+(?=\d)/, "")
  const body = fraction
    ? `${trimmed}.${fraction.slice(0, maximumFractionDigits)}`
    : trimmed
  return negative ? `-${body}` : body
}
