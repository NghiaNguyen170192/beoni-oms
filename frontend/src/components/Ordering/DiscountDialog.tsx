import { type FormEvent, useEffect, useState } from "react"

import type { DiscountType, DiscountUpdate } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { LoadingButton } from "@/components/ui/loading-button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { type MessageKey, useI18n } from "@/i18n"
import { formatAmountInput, parseAmountInput } from "@/lib/format"
import { DISCOUNT_TYPE_LABELS } from "@/lib/labels"

interface DiscountDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  current: { type: DiscountType | null; value: string | null }
  loading: boolean
  onApply: (discount: DiscountUpdate) => void
}

export function DiscountDialog({
  open,
  onOpenChange,
  title,
  current,
  loading,
  onApply,
}: DiscountDialogProps) {
  const { t } = useI18n()
  const [type, setType] = useState<DiscountType>("percent")
  const [value, setValue] = useState("")
  const [error, setError] = useState<MessageKey>()

  useEffect(() => {
    if (open) {
      setType(current.type ?? "percent")
      setValue(current.value?.replace(/\.0+$/, "") ?? "")
      setError(undefined)
    }
  }, [open, current.type, current.value])

  const submit = (event: FormEvent) => {
    event.preventDefault()
    const trimmed = value.trim()
    if (!/^\d+(\.\d{1,2})?$/.test(trimmed) || Number(trimmed) <= 0) {
      setError("ordering.discount.invalidValue")
      return
    }
    if (type === "percent" && Number(trimmed) > 100) {
      setError("ordering.discount.percentTooHigh")
      return
    }
    onApply({ discount_type: type, discount_value: trimmed })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-sm">
        <form onSubmit={submit}>
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
            <DialogDescription>
              {t("ordering.discount.description")}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-1.5">
              <Label>{t("ordering.discount.type")}</Label>
              <Select
                value={type}
                onValueChange={(next) => setType(next as DiscountType)}
              >
                <SelectTrigger
                  className="w-full"
                  aria-label={t("ordering.discount.type")}
                >
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {(["percent", "amount"] as const).map((option) => (
                    <SelectItem key={option} value={option}>
                      {t(DISCOUNT_TYPE_LABELS[option])}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="discount-value">
                {t("ordering.discount.value")}
              </Label>
              <Input
                id="discount-value"
                inputMode="decimal"
                value={type === "amount" ? formatAmountInput(value) : value}
                onChange={(e) =>
                  setValue(
                    type === "amount"
                      ? parseAmountInput(e.target.value)
                      : e.target.value,
                  )
                }
                autoFocus
              />
              {error && <p className="text-sm text-destructive">{t(error)}</p>}
            </div>
          </div>
          <DialogFooter className="gap-2">
            {current.type && (
              <Button
                type="button"
                variant="outline"
                disabled={loading}
                onClick={() => onApply({ discount_type: null })}
              >
                {t("ordering.discount.remove")}
              </Button>
            )}
            <LoadingButton type="submit" loading={loading}>
              {t("ordering.discount.apply")}
            </LoadingButton>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
