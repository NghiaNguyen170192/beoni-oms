import { createFileRoute } from "@tanstack/react-router"

import { PaymentMethodsSettings } from "@/components/Payments/PaymentMethodsSettings"
import BusinessSettings from "@/components/UserSettings/BusinessSettings"
import ChangePassword from "@/components/UserSettings/ChangePassword"
import DeleteAccount from "@/components/UserSettings/DeleteAccount"
import UserInformation from "@/components/UserSettings/UserInformation"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import useAuth from "@/hooks/useAuth"
import { type MessageKey, t, useI18n } from "@/i18n"
import { hasPermission } from "@/lib/permissions"

const tabsConfig: {
  value: string
  title: MessageKey
  component: React.ComponentType
}[] = [
  {
    value: "my-profile",
    title: "account.tabs.profile",
    component: UserInformation,
  },
  {
    value: "password",
    title: "account.tabs.password",
    component: ChangePassword,
  },
  {
    value: "business",
    title: "account.tabs.business",
    component: BusinessSettings,
  },
  {
    value: "danger-zone",
    title: "account.tabs.dangerZone",
    component: DeleteAccount,
  },
]

export const Route = createFileRoute("/_layout/settings")({
  component: UserSettings,
  head: () => ({
    meta: [
      {
        title: t("account.settings.pageTitle"),
      },
    ],
  }),
})

function UserSettings() {
  const { t } = useI18n()
  const { user: currentUser } = useAuth()
  const finalTabs = hasPermission(currentUser, "payments:configure")
    ? [
        ...tabsConfig,
        {
          value: "payment-methods",
          title: "payments.methods.title" as const,
          component: PaymentMethodsSettings,
        },
      ]
    : tabsConfig

  if (!currentUser) {
    return null
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          {t("nav.settings")}
        </h1>
        <p className="text-muted-foreground">
          {t("account.settings.description")}
        </p>
      </div>

      <Tabs defaultValue="my-profile">
        <TabsList>
          {finalTabs.map((tab) => (
            <TabsTrigger key={tab.value} value={tab.value}>
              {t(tab.title)}
            </TabsTrigger>
          ))}
        </TabsList>
        {finalTabs.map((tab) => (
          <TabsContent key={tab.value} value={tab.value}>
            <tab.component />
          </TabsContent>
        ))}
      </Tabs>
    </div>
  )
}
