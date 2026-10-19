import { type BatchStatus, ProductionApi } from "./api"

export const finishedGoodAvailabilityQueryOptions = () => ({
  queryKey: ["productionAvailability"],
  queryFn: () => ProductionApi.readAvailability(),
  refetchInterval: 15_000,
})

export const productionBatchesQueryOptions = (filters: {
  status?: BatchStatus
  plannedFrom?: string
  plannedTo?: string
  menuItemId?: string
  recipeId?: string
}) => ({
  queryKey: ["productionBatches", filters],
  queryFn: () => ProductionApi.readBatches(filters),
})

export const productionBatchQueryOptions = (batchId: string) => ({
  queryKey: ["productionBatch", batchId],
  queryFn: () => ProductionApi.readBatch(batchId),
})

export const productionTraceabilityQueryOptions = (batchId: string) => ({
  queryKey: ["productionTraceability", batchId],
  queryFn: () => ProductionApi.readTraceability(batchId),
})
