import type { ColumnDef } from "@tanstack/react-table"

import type { AuditLogPublic } from "@/client"
import { Badge } from "@/components/ui/badge"
import { useFormatters } from "@/hooks/useBusinessSettings"
import { type MessageKey, t } from "@/i18n"
import { displayName } from "@/lib/permissions"

const ENTITY_TYPE_LABELS: Record<string, MessageKey> = {
  user: "audit.entityTypes.user",
  order: "audit.entityTypes.order",
  menu_category: "audit.entityTypes.menu_category",
  menu_item: "audit.entityTypes.menu_item",
  inventory_item: "audit.entityTypes.inventory_item",
  stock_adjustment: "audit.entityTypes.stock_adjustment",
  business_settings: "audit.entityTypes.business_settings",
}

const ACTION_LABELS: Record<string, MessageKey> = {
  created: "audit.actions.created",
  updated: "audit.actions.updated",
  deleted: "audit.actions.deleted",
  activated: "audit.actions.activated",
  deactivated: "audit.actions.deactivated",
  role_changed: "audit.actions.role_changed",
  reordered: "audit.actions.reordered",
  image_changed: "audit.actions.image_changed",
  discount_changed: "audit.actions.discount_changed",
  line_discount_changed: "audit.actions.line_discount_changed",
  posted: "audit.actions.posted",
  reversed: "audit.actions.reversed",
  confirmed: "audit.actions.confirmed",
  paid: "audit.actions.paid",
  completed: "audit.actions.completed",
  cancelled: "audit.actions.cancelled",
  partially_refunded: "audit.actions.partially_refunded",
  refunded: "audit.actions.refunded",
}

/** Translate a server code, falling back to the raw code when unmapped. */
function label(labels: Record<string, MessageKey>, code: string): string {
  const key = labels[code]
  return key ? t(key) : code
}

function OccurredAt({ value }: { value: string }) {
  const { formatDateTime } = useFormatters()
  return <span className="whitespace-nowrap">{formatDateTime(value)}</span>
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—"
  if (typeof value === "string") return value
  return JSON.stringify(value)
}

function Changes({ changes }: { changes: AuditLogPublic["changes"] }) {
  if (!changes || Object.keys(changes).length === 0) {
    return <span className="text-muted-foreground">—</span>
  }
  return (
    <ul className="space-y-1 text-sm">
      {Object.entries(changes).map(([field, change]) => {
        const { old: oldValue, new: newValue } = (change ?? {}) as {
          old?: unknown
          new?: unknown
        }
        return (
          <li key={field}>
            <span className="font-medium">{field}</span>:{" "}
            <span className="text-muted-foreground">
              {formatValue(oldValue)}
            </span>{" "}
            → <span>{formatValue(newValue)}</span>
          </li>
        )
      })}
    </ul>
  )
}

export const columns: ColumnDef<AuditLogPublic>[] = [
  {
    accessorKey: "occurred_at",
    header: () => t("audit.when"),
    cell: ({ row }) => <OccurredAt value={row.original.occurred_at} />,
  },
  {
    accessorKey: "actor_email",
    header: () => t("audit.actor"),
    cell: ({ row }) => {
      const { actor_name, actor_email } = row.original
      return (
        <span
          className="text-muted-foreground"
          title={actor_email ?? undefined}
        >
          {actor_name || actor_email
            ? displayName(actor_name, actor_email)
            : t("audit.system")}
        </span>
      )
    },
  },
  {
    accessorKey: "entity_type",
    header: () => t("audit.entity"),
    cell: ({ row }) => (
      <div className="flex flex-col">
        <span className="font-medium" title={row.original.entity_type}>
          {label(ENTITY_TYPE_LABELS, row.original.entity_type)}
        </span>
        <span className="text-xs text-muted-foreground font-mono">
          {row.original.entity_id}
        </span>
      </div>
    ),
  },
  {
    accessorKey: "action",
    header: () => t("audit.action"),
    cell: ({ row }) => (
      <Badge variant="secondary" title={row.original.action}>
        {label(ACTION_LABELS, row.original.action)}
      </Badge>
    ),
  },
  {
    accessorKey: "changes",
    header: () => t("audit.changes"),
    cell: ({ row }) => <Changes changes={row.original.changes} />,
  },
]
