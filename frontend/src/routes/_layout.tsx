import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  createFileRoute,
  Outlet,
  redirect,
  useNavigate,
} from "@tanstack/react-router"
import { useEffect, useRef } from "react"
import { toast } from "sonner"
import { NotificationsService } from "@/client"
import { Footer } from "@/components/Common/Footer"
import AppSidebar from "@/components/Sidebar/AppSidebar"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import useAuth, { isLoggedIn } from "@/hooks/useAuth"
import { useBusinessSettings } from "@/hooks/useBusinessSettings"
import { useI18n } from "@/i18n"
import { hasPermission } from "@/lib/permissions"

export const Route = createFileRoute("/_layout")({
  component: Layout,
  beforeLoad: async () => {
    if (!isLoggedIn()) {
      throw redirect({
        to: "/login",
      })
    }
  },
})

function Layout() {
  // Subscribing here re-renders every page when the language changes.
  useI18n()
  useBusinessSettings()

  return (
    <SidebarProvider>
      <NotificationToasts />
      <AppSidebar />
      <SidebarInset>
        <header className="sticky top-0 z-10 flex h-16 shrink-0 items-center gap-2 border-b px-4">
          <SidebarTrigger className="-ml-1 text-muted-foreground" />
        </header>
        <main className="min-w-0 flex-1 p-4 sm:p-6 md:p-8">
          <div className="mx-auto w-full min-w-0 max-w-7xl">
            <Outlet />
          </div>
        </main>
        <Footer />
      </SidebarInset>
    </SidebarProvider>
  )
}

function NotificationToasts() {
  const { user } = useAuth()
  const { t } = useI18n()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const enabled = hasPermission(user, "notifications:read")
  const seen = useRef<{ ownerId: string; ids: Set<string> } | null>(null)
  const { data } = useQuery({
    queryKey: ["notifications", "unread", user?.id],
    queryFn: () =>
      NotificationsService.readNotifications({ unreadOnly: true, limit: 100 }),
    enabled,
    refetchInterval: enabled ? 15_000 : false,
    refetchIntervalInBackground: false,
  })
  const openNotification = useMutation({
    mutationFn: ({
      notificationId,
    }: {
      notificationId: string
      orderId: string
    }) =>
      NotificationsService.updateNotificationReadState({
        notificationId,
        requestBody: { is_read: true },
      }),
    onSuccess: (_notification, { orderId }) => {
      void queryClient.invalidateQueries({ queryKey: ["notifications"] })
      void navigate({
        to: "/orders",
        search: { orderId },
      })
    },
    onError: () => toast.error(t("common.somethingWentWrong")),
  })
  const openNotificationMutation = openNotification.mutate

  useEffect(() => {
    if (!data || !user) return
    const previous = seen.current
    if (previous?.ownerId === user.id) {
      for (const notification of data.data) {
        if (!previous.ids.has(notification.id)) {
          toast(t("notifications.toast.title"), {
            description: t("notifications.toast.description", {
              number: notification.order_number,
            }),
            action: {
              label: t("notifications.toast.open"),
              onClick: () =>
                openNotificationMutation({
                  notificationId: notification.id,
                  orderId: notification.order_id,
                }),
            },
            duration: 10_000,
          })
        }
      }
    }
    seen.current = {
      ownerId: user.id,
      ids: new Set(data.data.map((notification) => notification.id)),
    }
  }, [data, openNotificationMutation, t, user])

  return null
}

export default Layout
