import type { ColumnDef } from "@tanstack/react-table"

import type { UserPublic } from "@/client"
import { Badge } from "@/components/ui/badge"
import { t } from "@/i18n"
import { ROLE_LABELS } from "@/lib/permissions"
import { cn } from "@/lib/utils"
import { UserActionsMenu } from "./UserActionsMenu"

export type UserTableData = UserPublic & {
  isCurrentUser: boolean
}

export const columns: ColumnDef<UserTableData>[] = [
  {
    accessorKey: "full_name",
    header: () => t("common.fullName"),
    cell: ({ row }) => {
      const fullName = row.original.full_name
      return (
        <div className="flex items-center gap-2">
          <span
            className={cn("font-medium", !fullName && "text-muted-foreground")}
          >
            {fullName || t("common.notAvailable")}
          </span>
          {row.original.isCurrentUser && (
            <Badge variant="outline" className="text-xs">
              {t("admin.columns.you")}
            </Badge>
          )}
        </div>
      )
    },
  },
  {
    accessorKey: "email",
    header: () => t("common.email"),
    cell: ({ row }) => (
      <span className="text-muted-foreground">{row.original.email}</span>
    ),
  },
  {
    accessorKey: "role",
    header: () => t("common.role"),
    cell: ({ row }) => {
      const role = row.original.role ?? "cashier"
      return (
        <div className="flex items-center gap-2">
          <Badge variant={role === "owner" ? "default" : "secondary"}>
            {t(ROLE_LABELS[role])}
          </Badge>
          {row.original.is_superuser && (
            <Badge variant="outline">{t("admin.columns.superuser")}</Badge>
          )}
        </div>
      )
    },
  },
  {
    accessorKey: "is_active",
    header: () => t("common.status"),
    cell: ({ row }) => (
      <div className="flex items-center gap-2">
        <span
          className={cn(
            "size-2 rounded-full",
            row.original.is_active ? "bg-green-500" : "bg-gray-400",
          )}
        />
        <span className={row.original.is_active ? "" : "text-muted-foreground"}>
          {row.original.is_active ? t("common.active") : t("common.inactive")}
        </span>
      </div>
    ),
  },
  {
    id: "actions",
    enableSorting: false,
    header: () => <span className="sr-only">{t("common.actions")}</span>,
    cell: ({ row }) => (
      <div className="flex justify-end">
        <UserActionsMenu user={row.original} />
      </div>
    ),
  },
]
