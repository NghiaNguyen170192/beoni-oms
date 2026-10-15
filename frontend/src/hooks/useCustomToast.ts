import { toast } from "sonner"

import { t } from "@/i18n"

const useCustomToast = () => {
  const showSuccessToast = (description: string) => {
    toast.success(t("toast.success"), {
      description,
    })
  }

  const showErrorToast = (description: string) => {
    toast.error(t("toast.error"), {
      description,
    })
  }

  return { showSuccessToast, showErrorToast }
}

export default useCustomToast
