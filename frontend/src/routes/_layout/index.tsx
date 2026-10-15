import { createFileRoute } from "@tanstack/react-router"

import useAuth from "@/hooks/useAuth"
import { t, useI18n } from "@/i18n"
import { displayName } from "@/lib/permissions"

export const Route = createFileRoute("/_layout/")({
  component: Dashboard,
  head: () => ({
    meta: [
      {
        title: t("account.dashboard.pageTitle"),
      },
    ],
  }),
})

function Dashboard() {
  const { t } = useI18n()
  const { user: currentUser } = useAuth()

  return (
    <div>
      <div>
        <h1 className="text-2xl truncate max-w-sm">
          {t("account.dashboard.greeting", {
            name: currentUser
              ? displayName(currentUser.full_name, currentUser.email)
              : "",
          })}
        </h1>
        <p className="text-muted-foreground">
          {t("account.dashboard.welcome")}
        </p>
      </div>
    </div>
  )
}
