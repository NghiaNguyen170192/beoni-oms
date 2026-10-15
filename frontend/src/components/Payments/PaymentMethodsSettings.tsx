import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { type FormEvent, useState } from "react"

import {
  type ApiError,
  type PaymentMethodKind,
  PaymentsService,
} from "@/client"
import { Button } from "@/components/ui/button"
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
import useCustomToast from "@/hooks/useCustomToast"
import { type MessageKey, useI18n } from "@/i18n"
import { handleError } from "@/utils"

const KINDS: PaymentMethodKind[] = ["cash", "bank_transfer", "other"]

export function PaymentMethodsSettings() {
  const { t } = useI18n()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const queryClient = useQueryClient()
  const [name, setName] = useState("")
  const [kind, setKind] = useState<PaymentMethodKind>("other")

  const methods = useQuery({
    queryKey: ["payment-methods"],
    queryFn: () => PaymentsService.readPaymentMethods({}),
  })

  const create = useMutation({
    mutationFn: () =>
      PaymentsService.createPaymentMethod({
        requestBody: { name: name.trim(), kind },
      }),
    onSuccess: () => {
      showSuccessToast(t("payments.methods.created"))
      setName("")
      queryClient.invalidateQueries({ queryKey: ["payment-methods"] })
    },
    onError: (err: ApiError) => handleError.call(showErrorToast, err),
  })

  const deactivate = useMutation({
    mutationFn: (methodId: string) =>
      PaymentsService.updatePaymentMethod({
        methodId,
        requestBody: { is_active: false },
      }),
    onSuccess: () => {
      showSuccessToast(t("payments.methods.deactivated"))
      queryClient.invalidateQueries({ queryKey: ["payment-methods"] })
    },
    onError: (err: ApiError) => handleError.call(showErrorToast, err),
  })

  const submit = (event: FormEvent) => {
    event.preventDefault()
    create.mutate()
  }

  return (
    <div className="flex max-w-xl flex-col gap-4">
      <div>
        <h2 className="text-lg font-semibold">{t("payments.methods.title")}</h2>
        <p className="text-sm text-muted-foreground">
          {t("payments.methods.description")}
        </p>
      </div>
      <ul className="flex flex-col gap-2">
        {methods.data?.data.map((method) => (
          <li
            key={method.id}
            className="flex items-center justify-between rounded-md border px-3 py-2"
          >
            <span>
              {method.name} · {t(`payments.kind.${method.kind}` as MessageKey)}
              {!method.is_active && ` · ${t("common.inactive")}`}
            </span>
            {method.is_active && (
              <Button
                variant="outline"
                aria-label={t("payments.methods.deactivate", {
                  name: method.name,
                })}
                onClick={() => deactivate.mutate(method.id)}
              >
                {t("common.inactive")}
              </Button>
            )}
          </li>
        ))}
      </ul>
      <form className="flex flex-col gap-3" onSubmit={submit}>
        <div className="grid gap-1.5">
          <Label htmlFor="method-name">{t("payments.methods.name")}</Label>
          <Input
            id="method-name"
            value={name}
            maxLength={100}
            onChange={(event) => setName(event.target.value)}
            required
          />
        </div>
        <div className="grid gap-1.5">
          <Label>{t("payments.methods.kind")}</Label>
          <Select
            value={kind}
            onValueChange={(value) => setKind(value as PaymentMethodKind)}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {KINDS.map((value) => (
                <SelectItem key={value} value={value}>
                  {t(`payments.kind.${value}` as MessageKey)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <LoadingButton
          type="submit"
          className="w-fit"
          loading={create.isPending}
          disabled={!name.trim()}
        >
          {t("payments.methods.add")}
        </LoadingButton>
      </form>
    </div>
  )
}
