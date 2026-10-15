import type { ApiError } from "@/client"

export type Shortage = {
  item: string
  sku: string
  required: string
  available: string
  unit: string
}

/** 409 bodies from order completion carry the short ingredients. */
export function shortagesFrom(err: ApiError): Shortage[] | null {
  if (err.status !== 409 || !err.body || typeof err.body !== "object") {
    return null
  }
  const shortages = (err.body as { shortages?: unknown }).shortages
  if (!Array.isArray(shortages) || shortages.length === 0) return null
  return shortages as Shortage[]
}
