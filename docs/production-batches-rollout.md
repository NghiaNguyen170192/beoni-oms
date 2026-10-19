# Production batches rollout

## Before enabling production

1. Back up the database and deploy the application version with the production-batch migration. Keep the new application and schema together; do not downgrade the schema after batches, lots, or allocations have been recorded.
2. Review inventory items used as outputs and mark them as finished goods. Map each sellable menu product to the corresponding finished-good inventory item. Unmapped POS products do not create inventory movements.
3. Review or create recipe formulas as batch templates. Formulas describe ingredients per run; they do not deduct ingredients at POS checkout.
4. Confirm staff permissions for production planning, completion, reversal, and inventory reporting before the first live batch.

## Initial finished-goods count

Count sellable finished goods before enabling tracked POS sales. For each finished-good inventory item that has zero stock, post a physical-count adjustment from zero to the counted quantity. The adjustment creates an opening-stock lot and preserves the count in the inventory ledger. Do not create a production batch to represent stock that was made before rollout.

Opening-stock lots created by this workflow do not have an expiry date. Use production lots for subsequent batches when expiry tracking is needed. Verify the resulting inventory balance and lot availability in the inventory and production views before allowing POS sales.

## Daily operator workflow

1. Create a draft batch for the planned production date. Select one or more menu outputs and their planned quantities. If using a recipe formula, choose the formula version and run count; set this batch's planned output mix separately.
2. When production finishes, record actual ingredient usage, good output quantities, and waste, then complete the batch. Completion posts ingredient consumption and finished-good lots together.
3. Check the lot and available finished-good quantities before selling. POS consumes mapped finished goods from available lots and does not consume recipe ingredients. Tracked sales are rejected when finished-good lot stock is insufficient.
4. Use the production and inventory reports to review actual yield, waste, stock movements, and lot traceability. A returned sale restores stock to its source lot where permitted.
5. Do not edit completed batches to correct posted quantities. Reverse a posted batch with a reason when reversal rules permit, then record any corrected production as a new batch. Use a stock adjustment for count differences.

## Rollback limits

Production postings, POS lot allocations, returns, and inventory ledger movements are auditable records. Do not delete them or manually edit their database rows. A schema downgrade can remove production tables and is not a routine rollback once records exist. If rollout must be stopped, disable new production completion and use a forward application fix; coordinate any application rollback with a database backup and verify POS behavior, because older POS behavior may consume recipe ingredients at checkout.

Batch material cost is reported as an expense on the business-local finished date. A reversal offsets that expense on the business-local reversal date; it does not restate the earlier report period.
