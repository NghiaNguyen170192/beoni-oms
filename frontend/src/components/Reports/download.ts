export function reportFilename(name: string, dateFrom: string, dateTo: string) {
  return `${name}_${dateFrom}_${dateTo}.csv`
}

/** Save a CSV body returned by the generated client. */
export async function downloadCsv(
  load: () => Promise<unknown>,
  filename: string,
) {
  const body = await load()
  const text = typeof body === "string" ? body : String(body ?? "")
  const blob = new Blob([text], { type: "text/csv;charset=utf-8" })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}
