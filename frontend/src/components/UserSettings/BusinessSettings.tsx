import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { type BusinessSettingsUpdate, SettingsService } from "@/client"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import { Skeleton } from "@/components/ui/skeleton"
import useAuth from "@/hooks/useAuth"
import {
  businessSettingsQueryKey,
  useBusinessSettings,
  useFormatters,
} from "@/hooks/useBusinessSettings"
import useCustomToast from "@/hooks/useCustomToast"
import { t, useI18n } from "@/i18n"
import { hasPermission } from "@/lib/permissions"
import { handleError } from "@/utils"

const SUPPORTED_CURRENCIES = ["VND"] as const

const formSchema = z.object({
  business_name: z
    .string()
    .trim()
    .min(1, { error: () => t("account.business.nameRequired") })
    .max(255, { error: () => t("account.business.nameMax") }),
  currency_code: z.enum(SUPPORTED_CURRENCIES),
  timezone: z
    .string()
    .trim()
    .min(1, { error: () => t("account.business.timezoneRequired") }),
  allow_negative_stock: z.boolean(),
  tax_rate: z
    .string()
    .trim()
    .regex(/^\d{1,3}(\.\d{1,2})?$/, {
      error: () => t("account.business.taxRateFormat"),
    })
    .refine((value) => Number(value) <= 100, {
      error: () => t("account.business.taxRateRange"),
    }),
})

type FormData = z.infer<typeof formSchema>

const BusinessSettings = () => {
  const { t } = useI18n()
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const { user } = useAuth()
  const { data: settings, isPending } = useBusinessSettings()
  const { formatMoney, formatDateTime } = useFormatters()
  const canEdit = hasPermission(user, "settings:manage")

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    criteriaMode: "all",
    values: settings && {
      business_name: settings.business_name,
      currency_code: settings.currency_code as FormData["currency_code"],
      timezone: settings.timezone,
      allow_negative_stock: settings.allow_negative_stock,
      tax_rate: settings.tax_rate,
    },
  })

  const mutation = useMutation({
    mutationFn: (data: BusinessSettingsUpdate) =>
      SettingsService.updateBusinessSettings({ requestBody: data }),
    onSuccess: (updated) => {
      queryClient.setQueryData(businessSettingsQueryKey, updated)
      showSuccessToast(t("account.business.updated"))
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: businessSettingsQueryKey })
    },
  })

  if (isPending || !settings) {
    return (
      <div className="max-w-md flex flex-col gap-4 py-4">
        <Skeleton className="h-6 w-40" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    )
  }

  return (
    <div className="max-w-md">
      <h3 className="text-lg font-semibold py-4">
        {t("account.business.title")}
      </h3>
      <Form {...form}>
        <form
          onSubmit={form.handleSubmit((data) => mutation.mutate(data))}
          className="flex flex-col gap-4"
        >
          <FormField
            control={form.control}
            name="business_name"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t("account.business.name")}</FormLabel>
                <FormControl>
                  <Input type="text" disabled={!canEdit} {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="currency_code"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t("account.business.currency")}</FormLabel>
                <FormControl>
                  <Input type="text" readOnly disabled {...field} />
                </FormControl>
                <FormDescription>
                  {t("account.business.currencyHint", {
                    currencies: SUPPORTED_CURRENCIES.join(", "),
                  })}
                </FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="timezone"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t("account.business.timezone")}</FormLabel>
                <FormControl>
                  <Input
                    type="text"
                    placeholder="Asia/Ho_Chi_Minh"
                    disabled={!canEdit}
                    {...field}
                  />
                </FormControl>
                <FormDescription>
                  {t("account.business.timezoneHint")}
                </FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="tax_rate"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t("account.business.taxRate")}</FormLabel>
                <FormControl>
                  <Input
                    type="text"
                    inputMode="decimal"
                    disabled={!canEdit}
                    {...field}
                  />
                </FormControl>
                <FormDescription>
                  {t("account.business.taxRateHint")}
                </FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="allow_negative_stock"
            render={({ field }) => (
              <FormItem className="flex items-center gap-3 space-y-0">
                <FormControl>
                  <Checkbox
                    checked={field.value}
                    onCheckedChange={field.onChange}
                    disabled={!canEdit}
                  />
                </FormControl>
                <FormLabel className="font-normal">
                  {t("account.business.allowNegativeStock")}
                </FormLabel>
              </FormItem>
            )}
          />

          <p className="text-sm text-muted-foreground">
            {t("account.business.preview")} {formatMoney(45000)} ·{" "}
            {formatDateTime(settings.updated_at)}
          </p>

          {canEdit ? (
            <div>
              <LoadingButton
                type="submit"
                loading={mutation.isPending}
                disabled={!form.formState.isDirty}
              >
                {t("common.save")}
              </LoadingButton>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              {t("account.business.ownerOnly")}
            </p>
          )}
        </form>
      </Form>
    </div>
  )
}

export default BusinessSettings
