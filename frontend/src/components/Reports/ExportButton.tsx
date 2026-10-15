import { useState } from "react"

import { Button } from "@/components/ui/button"
import useCustomToast from "@/hooks/useCustomToast"
import { useI18n } from "@/i18n"

import { downloadCsv } from "./download"

export function ExportButton({
  testId,
  label,
  filename,
  load,
}: {
  testId: string
  label: string
  filename: string
  load: () => Promise<unknown>
}) {
  const { t } = useI18n()
  const { showErrorToast } = useCustomToast()
  const [pending, setPending] = useState(false)

  return (
    <Button
      type="button"
      variant="outline"
      data-testid={testId}
      disabled={pending}
      onClick={() => {
        setPending(true)
        void downloadCsv(load, filename)
          .catch(() => showErrorToast(t("common.error")))
          .finally(() => setPending(false))
      }}
    >
      {label}
    </Button>
  )
}
