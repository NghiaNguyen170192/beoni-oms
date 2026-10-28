import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import type { ColumnDef } from "@tanstack/react-table";
import { useMemo, useState } from "react";

import { CatalogService } from "@/client";
import { DataTable } from "@/components/Common/DataTable";
import type { BatchStatus, ProductionBatch, ProductionBatchSummary } from "@/components/Production/api";
import { ProductionBatchDetail } from "@/components/Production/ProductionBatchDetail";
import { ProductionBatchDialog } from "@/components/Production/ProductionBatchDialog";
import { productionBatchesQueryOptions } from "@/components/Production/queries";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import useAuth from "@/hooks/useAuth";
import { useFormatters } from "@/hooks/useBusinessSettings";
import { t as translate, useI18n } from "@/i18n";
import { hasPermission, requirePermission } from "@/lib/permissions";
import badgeStyles from "@/styles/badge.module.css";

export const Route = createFileRoute("/_layout/production")({
	component: Production,
	beforeLoad: requirePermission("production:view"),
	head: () => ({
		meta: [{ title: `${translate("production.title")} - Beoni OMS` }],
	}),
});

const ALL = "all";

const batchStatusClassMap: Record<BatchStatus, string> = {
	draft: badgeStyles.blue,
	completed: badgeStyles.green,
	cancelled: badgeStyles.red,
	reversed: badgeStyles.red,
};

function Production() {
	const { t } = useI18n();
	const { user } = useAuth();
	const { formatDateTime, formatMoney } = useFormatters();
	const canManage = hasPermission(user, "production:manage");
	const [status, setStatus] = useState<typeof ALL | BatchStatus>(ALL);
	const [plannedFrom, setPlannedFrom] = useState("");
	const [plannedTo, setPlannedTo] = useState("");
	const [menuItemId, setMenuItemId] = useState(ALL);
	const [selectedBatchId, setSelectedBatchId] = useState<string>();
	const [creating, setCreating] = useState(false);
	const [editing, setEditing] = useState<ProductionBatch>();

	const batches = useQuery(
		productionBatchesQueryOptions({
			status: status === ALL ? undefined : status,
			plannedFrom: plannedFrom || undefined,
			plannedTo: plannedTo || undefined,
			menuItemId: menuItemId === ALL ? undefined : menuItemId,
		}),
	);
	const menu = useQuery({
		queryKey: ["catalogItems", "production-filter"],
		queryFn: () => CatalogService.readItems({ isActive: true, limit: 500 }),
	});
	const rows = batches.data?.data ?? [];
	const menuItems = (menu.data?.data ?? []).filter((item) => item.product_type !== "non_stock");

	const columns = useMemo<ColumnDef<ProductionBatchSummary>[]>(
		() => [
			{
				accessorKey: "number",
				header: () => t("production.batch.numberHeader"),
				cell: ({ row }) => (
					<button type="button" className="font-medium hover:underline" onClick={() => setSelectedBatchId(row.original.id)}>
						{t("production.batch.number", { number: row.original.number })}
					</button>
				),
			},
			{
				accessorKey: "status",
				header: () => t("common.status"),
				cell: ({ row }) => <Badge className={batchStatusClassMap[row.original.status]}>{t(`production.status.${row.original.status}`)}</Badge>,
			},
			{
				id: "cost",
				accessorFn: (row) => Number(row.total_material_cost ?? -1),
				header: () => t("production.batch.materialCost"),
				cell: ({ row }) => (row.original.total_material_cost === null ? "—" : formatMoney(row.original.total_material_cost)),
			},
			{
				accessorKey: "planned_for",
				header: () => t("production.batch.plannedFor"),
			},
			{
				id: "finished_at",
				accessorFn: (row) => row.finished_at ?? "",
				header: () => t("production.batch.finishedAt"),
				cell: ({ row }) => (row.original.finished_at ? formatDateTime(row.original.finished_at) : "—"),
			},
		],
		[formatDateTime, formatMoney, t],
	);

	return (
		<div className="flex flex-col gap-4">
			<div className="flex flex-wrap items-start justify-between gap-3">
				<div>
					<h1 className="text-2xl font-bold tracking-tight">{t("production.title")}</h1>
					<p className="text-muted-foreground">{t("production.description")}</p>
				</div>
				{canManage && <Button onClick={() => setCreating(true)}>{t("production.batch.createAction")}</Button>}
			</div>

			<div className="grid min-w-0 gap-3 sm:grid-cols-2 lg:grid-cols-4">
				<div className="flex flex-col gap-1">
					<label htmlFor="production-status" className="text-sm font-medium">
						{t("common.status")}
					</label>
					<Select value={status} onValueChange={(value) => setStatus(value as typeof ALL | BatchStatus)}>
						<SelectTrigger id="production-status" className="w-full">
							<SelectValue />
						</SelectTrigger>
						<SelectContent>
							<SelectItem value={ALL}>{t("common.all")}</SelectItem>
							{(["draft", "completed", "cancelled", "reversed"] as const).map((value) => (
								<SelectItem key={value} value={value}>
									{t(`production.status.${value}`)}
								</SelectItem>
							))}
						</SelectContent>
					</Select>
				</div>

				<div className="flex flex-col gap-1">
					<label htmlFor="production-menu-item" className="text-sm font-medium">
						{t("production.batch.outputProduct")}
					</label>
					<Select value={menuItemId} onValueChange={setMenuItemId}>
						<SelectTrigger id="production-menu-item" className="w-full">
							<SelectValue />
						</SelectTrigger>
						<SelectContent>
							<SelectItem value={ALL}>{t("production.batch.allProducts")}</SelectItem>
							{menuItems.map((item) => (
								<SelectItem key={item.id} value={item.id}>
									{item.code} · {item.name}
								</SelectItem>
							))}
						</SelectContent>
					</Select>
				</div>
				<div className="flex flex-col gap-1">
					<label htmlFor="production-from" className="text-sm font-medium">
						{t("production.batch.plannedFrom")}
					</label>
					<Input id="production-from" type="date" value={plannedFrom} onChange={(event) => setPlannedFrom(event.target.value)} />
				</div>
				<div className="flex flex-col gap-1">
					<label htmlFor="production-to" className="text-sm font-medium">
						{t("production.batch.plannedTo")}
					</label>
					<Input id="production-to" type="date" value={plannedTo} onChange={(event) => setPlannedTo(event.target.value)} />
				</div>
			</div>

			{batches.isPending ? (
				<Skeleton className="h-48" />
			) : batches.error ? (
				<p role="alert" className="text-sm text-destructive">
					{batches.error.message}
				</p>
			) : (
				<DataTable columns={columns} data={rows} />
			)}

			{menu.error && (
				<p role="alert" className="text-sm text-destructive">
					{menu.error.message}
				</p>
			)}

			<ProductionBatchDialog
				open={creating || editing !== undefined}
				onOpenChange={(open) => {
					if (!open) {
						setCreating(false);
						setEditing(undefined);
					}
				}}
				batch={editing}
			/>
			<ProductionBatchDetail batchId={selectedBatchId} onClose={() => setSelectedBatchId(undefined)} onEdit={(batch) => setEditing(batch)} />
		</div>
	);
}
