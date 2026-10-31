import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { Bell, Check, Circle } from "lucide-react"
import { useState } from "react"

import { NotificationsService } from "@/client"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import useAuth from "@/hooks/useAuth"
import { useFormatters } from "@/hooks/useBusinessSettings"
import { type MessageKey, t as translate, useI18n } from "@/i18n"
import { requirePermission } from "@/lib/permissions"

export const Route = createFileRoute("/_layout/notifications")({
  component: Notifications,
  beforeLoad: requirePermission("notifications:read"),
  head: () => ({
    meta: [{ title: translate("notifications.pageTitle") }],
  }),
})

const PAGE_SIZE = 50

function Notifications() {
  const { t } = useI18n()
  const { user } = useAuth()
  const { formatDateTime } = useFormatters()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [page, setPage] = useState(0)
  const queryKey = ["notifications", user?.id, page]
  const { data, isPending, isError } = useQuery({
    queryKey,
    queryFn: () =>
      NotificationsService.readNotifications({
        skip: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      }),
  })
  const updateReadState = useMutation({
    mutationFn: ({
      notificationId,
      isRead,
    }: {
      notificationId: string
      isRead: boolean
    }) =>
      NotificationsService.updateNotificationReadState({
        notificationId,
        requestBody: { is_read: isRead },
      }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["notifications"] }),
  })

  const pageCount = Math.max(1, Math.ceil((data?.count ?? 0) / PAGE_SIZE))

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1
          className="text-2xl font-semibold"
          data-testid="notifications-title"
        >
          {t("notifications.title")}
        </h1>
        <p className="text-muted-foreground">
          {t("notifications.description")}
        </p>
        {data && (
          <p
            className="text-sm font-medium"
            data-testid="notifications-unread-count"
          >
            {t("notifications.unreadCount", { count: data.unread_count })}
          </p>
        )}
      </header>

      {isError && (
        <p role="alert" className="text-destructive">
          {t("common.somethingWentWrong")}
        </p>
      )}
      {isPending ? (
        <div className="space-y-3">
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
        </div>
      ) : isError ? null : data?.data.length ? (
        <>
          <ul className="divide-y rounded-md border">
            {data.data.map((notification) => {
              const isRead = notification.read_at !== null
              const label: MessageKey = isRead
                ? "notifications.read"
                : "notifications.unread"
              const openNotification = () => {
                const openOrder = () =>
                  void navigate({
                    to: "/orders",
                    search: { orderId: notification.order_id },
                  })
                if (isRead) {
                  openOrder()
                } else {
                  updateReadState.mutate(
                    { notificationId: notification.id, isRead: true },
                    { onSuccess: openOrder },
                  )
                }
              }
              return (
                <li
                  key={notification.id}
                  className="flex flex-wrap items-center justify-between gap-4 p-4"
                  data-testid={`notification-${notification.order_id}`}
                >
                  <div className="flex min-w-0 items-center gap-3">
                    {isRead ? (
                      <Check
                        aria-hidden="true"
                        className="size-5 text-muted-foreground"
                      />
                    ) : (
                      <Circle
                        aria-hidden="true"
                        className="size-5 fill-primary text-primary"
                      />
                    )}
                    <div className="min-w-0">
                      <Button
                        variant="link"
                        className="font-medium underline-offset-4 hover:underline"
                        data-testid={`notification-open-${notification.order_id}`}
                        onClick={openNotification}
                      >
                        {notification.order_number}
                      </Button>
                      <p className="text-sm text-muted-foreground">
                        {formatDateTime(notification.created_at)}
                      </p>
                    </div>
                    <Badge variant={isRead ? "secondary" : "default"}>
                      {t(label)}
                    </Badge>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={updateReadState.isPending}
                    data-testid={`notification-toggle-${notification.order_id}`}
                    onClick={() =>
                      updateReadState.mutate({
                        notificationId: notification.id,
                        isRead: !isRead,
                      })
                    }
                  >
                    {isRead ? (
                      <Bell aria-hidden="true" />
                    ) : (
                      <Check aria-hidden="true" />
                    )}
                    {t(
                      isRead
                        ? "notifications.markUnread"
                        : "notifications.markRead",
                    )}
                  </Button>
                </li>
              )
            })}
          </ul>
          <p className="text-sm text-muted-foreground">
            {t("notifications.pagination", {
              count: data.count,
              page: page + 1,
              pages: pageCount,
            })}
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              disabled={page === 0}
              onClick={() => setPage((current) => current - 1)}
            >
              {t("notifications.newer")}
            </Button>
            <Button
              variant="outline"
              disabled={page + 1 >= pageCount}
              onClick={() => setPage((current) => current + 1)}
            >
              {t("notifications.older")}
            </Button>
          </div>
        </>
      ) : (
        <p className="py-8 text-center text-muted-foreground">
          {t("notifications.empty")}
        </p>
      )}
      {updateReadState.isError && (
        <p role="alert" className="text-destructive">
          {t("common.somethingWentWrong")}
        </p>
      )}
    </div>
  )
}
