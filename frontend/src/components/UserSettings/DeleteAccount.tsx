import { useI18n } from "@/i18n"
import DeleteConfirmation from "./DeleteConfirmation"

const DeleteAccount = () => {
  const { t } = useI18n()

  return (
    <div className="max-w-md mt-4 rounded-lg border border-destructive/50 p-4">
      <h3 className="font-semibold text-destructive">
        {t("account.delete.title")}
      </h3>
      <p className="mt-1 text-sm text-muted-foreground">
        {t("account.delete.description")}
      </p>
      <DeleteConfirmation />
    </div>
  )
}

export default DeleteAccount
