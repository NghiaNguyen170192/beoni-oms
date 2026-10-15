import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, redirect } from "@tanstack/react-router"
import { type FormEvent, Suspense, useState } from "react"

import { AuditService, UsersService } from "@/client"
import { columns } from "@/components/Audit/columns"
import { DataTable } from "@/components/Common/DataTable"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { t as translate, useI18n } from "@/i18n"
import { hasPermission } from "@/lib/permissions"

const PAGE_SIZE = 100

type Filters = { entityType: string; entityId: string }

function getAuditLogQueryOptions(filters: Filters, page: number) {
  return {
    queryFn: () =>
      AuditService.readAuditLog({
        entityType: filters.entityType || undefined,
        entityId: filters.entityId || undefined,
        skip: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      }),
    queryKey: ["auditLog", filters, page],
  }
}

export const Route = createFileRoute("/_layout/admin_/audit-log")({
  component: AuditLog,
  beforeLoad: async () => {
    const user = await UsersService.readUserMe()
    if (!hasPermission(user, "audit:read")) {
      throw redirect({ to: "/" })
    }
  },
  head: () => ({
    meta: [{ title: `${translate("nav.auditLog")} - Beoni OMS` }],
  }),
})

function AuditLogTableContent({
  filters,
  page,
  onPageChange,
}: {
  filters: Filters
  page: number
  onPageChange: (page: number) => void
}) {
  const { t } = useI18n()
  const { data } = useSuspenseQuery(getAuditLogQueryOptions(filters, page))
  const pageCount = Math.max(1, Math.ceil(data.count / PAGE_SIZE))

  return (
    <div className="flex flex-col gap-4">
      <DataTable columns={columns} data={data.data} />
      {pageCount > 1 && (
        <div className="flex items-center justify-end gap-2 text-sm">
          <span className="text-muted-foreground">
            {t("audit.pageSummary", {
              count: data.count,
              page: page + 1,
              pageCount,
            })}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page === 0}
            onClick={() => onPageChange(page - 1)}
          >
            {t("audit.newer")}
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={page + 1 >= pageCount}
            onClick={() => onPageChange(page + 1)}
          >
            {t("audit.older")}
          </Button>
        </div>
      )}
    </div>
  )
}

function PendingAuditLog() {
  return (
    <div className="flex flex-col gap-2">
      {Array.from({ length: 5 }).map((_, index) => (
        <Skeleton key={index} className="h-10 w-full" />
      ))}
    </div>
  )
}

function AuditLog() {
  const { t } = useI18n()
  const [draft, setDraft] = useState<Filters>({ entityType: "", entityId: "" })
  const [filters, setFilters] = useState<Filters>(draft)
  const [page, setPage] = useState(0)

  const applyFilters = (event: FormEvent) => {
    event.preventDefault()
    setFilters({
      entityType: draft.entityType.trim(),
      entityId: draft.entityId.trim(),
    })
    setPage(0)
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          {t("nav.auditLog")}
        </h1>
        <p className="text-muted-foreground">{t("audit.description")}</p>
      </div>

      <form
        onSubmit={applyFilters}
        className="flex flex-col gap-3 sm:flex-row sm:items-end"
      >
        <div className="grid gap-1.5">
          <Label htmlFor="audit-entity-type">{t("audit.entityType")}</Label>
          <Input
            id="audit-entity-type"
            placeholder={t("audit.entityTypePlaceholder")}
            value={draft.entityType}
            onChange={(e) => setDraft({ ...draft, entityType: e.target.value })}
          />
        </div>
        <div className="grid gap-1.5 sm:min-w-80">
          <Label htmlFor="audit-entity-id">{t("audit.entityId")}</Label>
          <Input
            id="audit-entity-id"
            placeholder={t("audit.entityIdPlaceholder")}
            value={draft.entityId}
            onChange={(e) => setDraft({ ...draft, entityId: e.target.value })}
          />
        </div>
        <Button type="submit">{t("audit.filter")}</Button>
      </form>

      <Suspense fallback={<PendingAuditLog />}>
        <AuditLogTableContent
          filters={filters}
          page={page}
          onPageChange={setPage}
        />
      </Suspense>
    </div>
  )
}
