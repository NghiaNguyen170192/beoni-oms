import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { type FormEvent, useEffect, useState } from "react"

import { type OrderFeeTypePublic, SettingsService } from "@/client"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import {
  businessSettingsQueryKey,
  useBusinessSettings,
} from "@/hooks/useBusinessSettings"
import useCustomToast from "@/hooks/useCustomToast"
import { t, useI18n } from "@/i18n"
import { requirePermission } from "@/lib/permissions"
import { handleError } from "@/utils"

const feeTypesQueryKey = ["orderFeeTypes", "all"]

export const Route = createFileRoute("/_layout/admin_/fees")({
  component: PosFeeSettings,
  beforeLoad: requirePermission("settings:manage"),
  head: () => ({
    meta: [{ title: `${t("admin.fees.title")} - Beoni OMS` }],
  }),
})

function PosFeeSettings() {
  const { t } = useI18n()
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const { data: settings, isPending: settingsPending } = useBusinessSettings()
  const { data: feeTypes, isPending: feeTypesPending } = useQuery({
    queryKey: feeTypesQueryKey,
    queryFn: () => SettingsService.readAllOrderFeeTypes(),
  })
  const [businessName, setBusinessName] = useState("")
  const [newFeeName, setNewFeeName] = useState("")
  const [taxRate, setTaxRate] = useState("")
  const [taxRateError, setTaxRateError] = useState("")

  useEffect(() => {
    if (settings) {
      setBusinessName(settings.business_name)
      setTaxRate(settings.tax_rate)
    }
  }, [settings])

  const updateBusinessName = useMutation({
    mutationFn: (name: string) =>
      SettingsService.updateBusinessName({
        requestBody: { business_name: name },
      }),
    onSuccess: (updated) => {
      queryClient.setQueryData(businessSettingsQueryKey, updated)
      showSuccessToast(t("admin.fees.shopNameUpdated"))
    },
    onError: handleError.bind(showErrorToast),
  })

  const updateTaxRate = useMutation({
    mutationFn: (rate: string) =>
      SettingsService.updateBusinessTaxRate({
        requestBody: { tax_rate: rate },
      }),
    onSuccess: (updated) => {
      queryClient.setQueryData(businessSettingsQueryKey, updated)
      setTaxRate(updated.tax_rate)
      setTaxRateError("")
      showSuccessToast(t("admin.fees.taxRateUpdated"))
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: businessSettingsQueryKey })
    },
  })

  const createFee = useMutation({
    mutationFn: (name: string) =>
      SettingsService.createOrderFeeType({
        requestBody: { name, is_enabled: true },
      }),
    onSuccess: () => {
      setNewFeeName("")
      void queryClient.invalidateQueries({ queryKey: ["orderFeeTypes"] })
      showSuccessToast(t("admin.fees.feeCreated"))
    },
    onError: handleError.bind(showErrorToast),
  })

  const updateFee = useMutation({
    mutationFn: ({
      feeTypeId,
      name,
      isEnabled,
    }: {
      feeTypeId: string
      name?: string
      isEnabled?: boolean
    }) =>
      SettingsService.updateOrderFeeType({
        feeTypeId,
        requestBody: {
          ...(name === undefined ? {} : { name }),
          ...(isEnabled === undefined ? {} : { is_enabled: isEnabled }),
        },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["orderFeeTypes"] })
      showSuccessToast(t("admin.fees.feeUpdated"))
    },
    onError: handleError.bind(showErrorToast),
  })

  function submitBusinessName(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const name = businessName.trim()
    if (name && name !== settings?.business_name) {
      updateBusinessName.mutate(name)
    }
  }

  function submitTaxRate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const rate = taxRate.trim()
    if (!/^\d{1,3}(\.\d{1,2})?$/.test(rate)) {
      setTaxRateError(t("account.business.taxRateFormat"))
      return
    }
    if (Number(rate) > 100) {
      setTaxRateError(t("account.business.taxRateRange"))
      return
    }
    if (rate !== settings?.tax_rate) updateTaxRate.mutate(rate)
  }

  function submitNewFee(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const name = newFeeName.trim()
    if (name) createFee.mutate(name)
  }

  return (
    <div className="flex max-w-2xl flex-col gap-8">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">
          {t("admin.fees.title")}
        </h1>
        <p className="text-muted-foreground">{t("admin.fees.description")}</p>
      </header>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">{t("admin.fees.shopName")}</h2>
        {settingsPending ? (
          <Skeleton className="h-10 w-full" />
        ) : (
          <form
            onSubmit={submitBusinessName}
            className="flex flex-col gap-3 sm:flex-row"
          >
            <Label htmlFor="business-name" className="sr-only">
              {t("admin.fees.shopName")}
            </Label>
            <Input
              id="business-name"
              value={businessName}
              onChange={(event) => setBusinessName(event.target.value)}
              required
              maxLength={255}
              disabled={updateBusinessName.isPending}
            />
            <Button
              type="submit"
              disabled={
                updateBusinessName.isPending ||
                !businessName.trim() ||
                businessName.trim() === settings?.business_name
              }
            >
              {t("common.save")}
            </Button>
          </form>
        )}
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">
          {t("account.business.taxRate")}
        </h2>
        {settingsPending ? (
          <Skeleton className="h-10 w-full" />
        ) : (
          <form
            onSubmit={submitTaxRate}
            className="flex flex-col gap-3 sm:flex-row"
          >
            <Label htmlFor="business-tax-rate" className="sr-only">
              {t("account.business.taxRate")}
            </Label>
            <Input
              id="business-tax-rate"
              type="text"
              inputMode="decimal"
              value={taxRate}
              onChange={(event) => {
                setTaxRate(event.target.value)
                setTaxRateError("")
              }}
              aria-invalid={Boolean(taxRateError)}
              disabled={updateTaxRate.isPending}
            />
            <Button
              type="submit"
              disabled={
                updateTaxRate.isPending || taxRate.trim() === settings?.tax_rate
              }
            >
              {t("common.save")}
            </Button>
            {taxRateError && (
              <p role="alert" className="text-sm text-destructive">
                {taxRateError}
              </p>
            )}
          </form>
        )}
        <p className="text-sm text-muted-foreground">
          {t("account.business.taxRateHint")}
        </p>
      </section>

      <section className="flex flex-col gap-4">
        <h2 className="text-lg font-semibold">{t("admin.fees.title")}</h2>
        <form onSubmit={submitNewFee} className="flex gap-3">
          <Label htmlFor="new-fee-name" className="sr-only">
            {t("admin.fees.newFeeName")}
          </Label>
          <Input
            id="new-fee-name"
            value={newFeeName}
            onChange={(event) => setNewFeeName(event.target.value)}
            required
            maxLength={255}
            disabled={createFee.isPending}
          />
          <Button type="submit" disabled={createFee.isPending}>
            {t("admin.fees.addFee")}
          </Button>
        </form>
        {feeTypesPending ? (
          <Skeleton className="h-24 w-full" />
        ) : feeTypes?.length ? (
          <ul className="divide-y rounded-md border">
            {feeTypes.map((feeType) => (
              <li
                key={feeType.id}
                className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center"
              >
                <FeeTypeRow
                  feeType={feeType}
                  disabled={updateFee.isPending}
                  onRename={(name) =>
                    updateFee.mutate({ feeTypeId: feeType.id, name })
                  }
                  onToggle={(isEnabled) =>
                    updateFee.mutate({
                      feeTypeId: feeType.id,
                      isEnabled,
                    })
                  }
                />
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">
            {t("admin.fees.empty")}
          </p>
        )}
      </section>
    </div>
  )
}

function FeeTypeRow({
  feeType,
  disabled,
  onRename,
  onToggle,
}: {
  feeType: OrderFeeTypePublic
  disabled: boolean
  onRename: (name: string) => void
  onToggle: (isEnabled: boolean) => void
}) {
  const { t } = useI18n()
  const [name, setName] = useState(feeType.name)

  useEffect(() => setName(feeType.name), [feeType.name])

  function submitName(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const nextName = name.trim()
    if (nextName && nextName !== feeType.name) onRename(nextName)
  }

  return (
    <>
      <form onSubmit={submitName} className="flex flex-1 gap-3">
        <Label htmlFor={`fee-name-${feeType.id}`} className="sr-only">
          {t("admin.fees.feeName", { name: feeType.name })}
        </Label>
        <Input
          id={`fee-name-${feeType.id}`}
          value={name}
          onChange={(event) => setName(event.target.value)}
          required
          maxLength={255}
          disabled={disabled}
        />
        <Button
          type="submit"
          variant="outline"
          disabled={disabled || !name.trim() || name.trim() === feeType.name}
        >
          {t("common.save")}
        </Button>
      </form>
      <div className="flex items-center gap-2 sm:min-w-40">
        <Checkbox
          id={`fee-enabled-${feeType.id}`}
          checked={feeType.is_enabled}
          onCheckedChange={(checked) => onToggle(checked === true)}
          disabled={disabled}
        />
        <Label htmlFor={`fee-enabled-${feeType.id}`}>
          {t("admin.fees.enabledForPos")}
        </Label>
      </div>
    </>
  )
}
