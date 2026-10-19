import {
  type FinishedGoodAvailabilityPublic,
  type ProductionBatchComplete,
  type ProductionBatchCreate,
  type ProductionBatchPublic,
  type ProductionBatchStatus,
  type ProductionBatchSummary,
  type ProductionBatchTemplateCreate,
  type ProductionBatchTemplatePublic,
  type ProductionBatchUpdate,
  ProductionService,
} from "@/client"

export type BatchStatus = ProductionBatchStatus
export type ProductionBatch = ProductionBatchPublic
export type { ProductionBatchSummary }
export type FinishedGoodAvailability = FinishedGoodAvailabilityPublic

export const ProductionApi = {
  readAvailability() {
    return ProductionService.readFinishedGoodAvailability()
  },
  readBatches(
    query: {
      status?: BatchStatus
      plannedFrom?: string
      plannedTo?: string
      menuItemId?: string
      recipeId?: string
    } = {},
  ) {
    return ProductionService.readBatches({
      status: query.status,
      plannedFrom: query.plannedFrom,
      plannedTo: query.plannedTo,
      menuItemId: query.menuItemId,
      recipeId: query.recipeId,
      limit: 500,
    })
  },
  readBatch(batchId: string) {
    return ProductionService.readBatch({ batchId })
  },
  readTraceability(batchId: string) {
    return ProductionService.readBatchTraceability({ batchId })
  },
  createBatch(requestBody: ProductionBatchCreate) {
    return ProductionService.createBatch({ requestBody })
  },
  updateBatch(batchId: string, requestBody: ProductionBatchUpdate) {
    return ProductionService.updateBatch({ batchId, requestBody })
  },
  completeBatch(
    batchId: string,
    idempotencyKey: string,
    requestBody: ProductionBatchComplete,
  ) {
    return ProductionService.completeBatch({
      batchId,
      idempotencyKey,
      requestBody,
    })
  },
  reverseBatch(batchId: string, idempotencyKey: string, reason: string) {
    return ProductionService.reverseBatch({
      batchId,
      idempotencyKey,
      requestBody: { reason },
    })
  },
  readBatchTemplates() {
    return ProductionService.readBatchTemplates()
  },
  createBatchTemplate(requestBody: ProductionBatchTemplateCreate) {
    return ProductionService.createBatchTemplate({ requestBody })
  },
  deleteBatchTemplate(templateId: string) {
    return ProductionService.deleteBatchTemplate({ templateId })
  },
}

export type ProductionBatchTemplate = ProductionBatchTemplatePublic
