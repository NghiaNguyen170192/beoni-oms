import { useCallback, useRef } from "react"

function newKey(): string {
  if (typeof crypto.randomUUID === "function") {
    return crypto.randomUUID()
  }
  // randomUUID needs a secure context; tablets on plain http over LAN lack one.
  const bytes = crypto.getRandomValues(new Uint8Array(16))
  bytes[6] = (bytes[6] & 0x0f) | 0x40
  bytes[8] = (bytes[8] & 0x3f) | 0x80
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("")
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}

/**
 * One key per user action: `current()` returns the same key until `reset()`,
 * so retrying a failed or timed-out request cannot apply it twice.
 */
export function useIdempotencyKey() {
  const key = useRef<string | null>(null)

  const current = useCallback(() => {
    key.current ??= newKey()
    return key.current
  }, [])

  const reset = useCallback(() => {
    key.current = null
  }, [])

  return { current, reset }
}
