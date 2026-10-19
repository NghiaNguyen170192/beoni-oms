import type { Shortage } from "@/components/Recipes/shortages"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useI18n } from "@/i18n"
import { formatNumber } from "@/lib/format"

export function ShortageDialog({
  shortages,
  onClose,
}: {
  shortages: Shortage[] | undefined
  onClose: () => void
}) {
  const { t } = useI18n()
  return (
    <Dialog
      open={shortages !== undefined}
      onOpenChange={(open) => !open && onClose()}
    >
      <DialogContent data-testid="shortage-dialog">
        <DialogHeader>
          <DialogTitle>{t("ordering.stockShortage.title")}</DialogTitle>
          <DialogDescription>
            {t("ordering.stockShortage.description")}
          </DialogDescription>
        </DialogHeader>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("ordering.stockShortage.item")}</TableHead>
              <TableHead className="text-right">
                {t("ordering.stockShortage.required")}
              </TableHead>
              <TableHead className="text-right">
                {t("ordering.stockShortage.available")}
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {shortages?.map((row) => (
              <TableRow key={row.sku}>
                <TableCell>
                  {row.item}
                  <div className="text-xs text-muted-foreground">{row.sku}</div>
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatNumber(row.required)} {row.unit}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatNumber(row.available)} {row.unit}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <DialogFooter>
          <Button onClick={onClose}>{t("common.close")}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
