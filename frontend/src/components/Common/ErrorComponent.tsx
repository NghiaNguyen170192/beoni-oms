import { Link } from "@tanstack/react-router"
import { Button } from "@/components/ui/button"
import { useI18n } from "@/i18n"

const ErrorComponent = () => {
  const { t } = useI18n()

  return (
    <div
      className="flex min-h-screen items-center justify-center flex-col p-4"
      data-testid="error-component"
    >
      <div className="flex items-center z-10">
        <div className="flex flex-col ml-4 items-center justify-center p-4">
          <span className="text-6xl md:text-8xl font-bold leading-none mb-4">
            {t("common.error")}
          </span>
          <span className="text-2xl font-bold mb-2">{t("errorPage.oops")}</span>
        </div>
      </div>

      <p className="text-lg text-muted-foreground mb-4 text-center z-10">
        {t("errorPage.description")}
      </p>
      <Link to="/">
        <Button>{t("errorPage.goHome")}</Button>
      </Link>
    </div>
  )
}

export default ErrorComponent
