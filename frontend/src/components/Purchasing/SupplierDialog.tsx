import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"

import { PurchasingService, type SupplierPublic } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { useI18n } from "@/i18n"
import { handleError } from "@/utils"

type FormState = {
  name: string
  code: string
  phone: string
  email: string
  address: string
  tax_code: string
  contact_person: string
  notes: string
  is_active: boolean
}

const empty = (): FormState => ({
  name: "",
  code: "",
  phone: "",
  email: "",
  address: "",
  tax_code: "",
  contact_person: "",
  notes: "",
  is_active: true,
})

function fromSupplier(supplier: SupplierPublic): FormState {
  return {
    name: supplier.name,
    code: supplier.code ?? "",
    phone: supplier.phone ?? "",
    email: supplier.email ?? "",
    address: supplier.address ?? "",
    tax_code: supplier.tax_code ?? "",
    contact_person: supplier.contact_person ?? "",
    notes: supplier.notes ?? "",
    is_active: supplier.is_active,
  }
}

export function SupplierDialog({
  open,
  onOpenChange,
  supplier,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  supplier?: SupplierPublic
}) {
  const { t } = useI18n()
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [form, setForm] = useState<FormState>(
    supplier ? fromSupplier(supplier) : empty(),
  )

  const save = useMutation({
    mutationFn: () => {
      const body = {
        name: form.name.trim(),
        code: form.code.trim() || null,
        phone: form.phone.trim() || null,
        email: form.email.trim() || null,
        address: form.address.trim() || null,
        tax_code: form.tax_code.trim() || null,
        contact_person: form.contact_person.trim() || null,
        notes: form.notes.trim() || null,
        is_active: form.is_active,
      }
      return supplier
        ? PurchasingService.updateSupplier({
            supplierId: supplier.id,
            requestBody: body,
          })
        : PurchasingService.createSupplier({ requestBody: body })
    },
    onSuccess: () => {
      showSuccessToast(
        supplier
          ? t("purchasing.suppliers.updated")
          : t("purchasing.suppliers.created"),
      )
      onOpenChange(false)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["suppliers"] }),
  })

  const set = (field: keyof FormState) => (value: string) =>
    setForm((current) => ({ ...current, [field]: value }))

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (next) setForm(supplier ? fromSupplier(supplier) : empty())
        onOpenChange(next)
      }}
    >
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {supplier
              ? t("purchasing.suppliers.edit")
              : t("purchasing.suppliers.add")}
          </DialogTitle>
        </DialogHeader>
        <div className="grid gap-3">
          <Field
            id="supplier-name"
            label={t("purchasing.suppliers.field.name")}
            value={form.name}
            onChange={set("name")}
          />
          <Field
            id="supplier-code"
            label={t("purchasing.suppliers.field.code")}
            value={form.code}
            onChange={set("code")}
          />
          <Field
            id="supplier-phone"
            label={t("purchasing.suppliers.field.phone")}
            value={form.phone}
            onChange={set("phone")}
          />
          <Field
            id="supplier-email"
            label={t("purchasing.suppliers.field.email")}
            value={form.email}
            onChange={set("email")}
          />
          <Field
            id="supplier-address"
            label={t("purchasing.suppliers.field.address")}
            value={form.address}
            onChange={set("address")}
          />
          <Field
            id="supplier-tax"
            label={t("purchasing.suppliers.field.taxCode")}
            value={form.tax_code}
            onChange={set("tax_code")}
          />
          <Field
            id="supplier-contact"
            label={t("purchasing.suppliers.field.contact")}
            value={form.contact_person}
            onChange={set("contact_person")}
          />
          <Field
            id="supplier-notes"
            label={t("purchasing.suppliers.field.notes")}
            value={form.notes}
            onChange={set("notes")}
          />
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  is_active: event.target.checked,
                }))
              }
            />
            {t("purchasing.suppliers.field.active")}
          </label>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t("common.cancel")}
          </Button>
          <LoadingButton
            loading={save.isPending}
            disabled={!form.name.trim()}
            onClick={() => save.mutate()}
          >
            {t("common.save")}
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function Field({
  id,
  label,
  value,
  onChange,
}: {
  id: string
  label: string
  value: string
  onChange: (value: string) => void
}) {
  return (
    <div className="grid gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  )
}
