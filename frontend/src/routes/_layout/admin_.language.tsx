import { useMutation, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Check } from "lucide-react"

import { SettingsService } from "@/client"
import { Skeleton } from "@/components/ui/skeleton"
import {
  businessSettingsQueryKey,
  useBusinessSettings,
} from "@/hooks/useBusinessSettings"
import useCustomToast from "@/hooks/useCustomToast"
import {
  LANGUAGE_NAMES,
  LANGUAGES,
  type Language,
  setLanguage,
  t,
  useI18n,
} from "@/i18n"
import { requirePermission } from "@/lib/permissions"
import { cn } from "@/lib/utils"
import { handleError } from "@/utils"

export const Route = createFileRoute("/_layout/admin_/language")({
  component: LanguageSettings,
  beforeLoad: requirePermission("settings:manage"),
  head: () => ({
    meta: [{ title: `${t("language.title")} - Beoni OMS` }],
  }),
})

function LanguageSettings() {
  const { t } = useI18n()
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const { data: settings } = useBusinessSettings()

  const mutation = useMutation({
    mutationFn: (next: Language) =>
      SettingsService.updateLanguage({ requestBody: { language: next } }),
    onSuccess: (updated) => {
      queryClient.setQueryData(businessSettingsQueryKey, updated)
      setLanguage(updated.language)
      showSuccessToast(t("language.saved"))
    },
    onError: handleError.bind(showErrorToast),
  })

  const selected = mutation.isPending ? mutation.variables : settings?.language

  return (
    <div className="flex max-w-xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          {t("language.title")}
        </h1>
        <p className="text-muted-foreground">{t("language.description")}</p>
      </div>

      {settings ? (
        <div
          role="radiogroup"
          aria-label={t("language.label")}
          className="flex flex-col gap-2"
        >
          {LANGUAGES.map((option) => {
            const checked = option === selected
            return (
              // biome-ignore lint/a11y/useSemanticElements: styled radio card
              <button
                key={option}
                type="button"
                role="radio"
                aria-checked={checked}
                lang={option}
                disabled={mutation.isPending}
                onClick={() => {
                  if (option !== settings.language) mutation.mutate(option)
                }}
                className={cn(
                  "flex items-center justify-between rounded-lg border p-4 text-left transition-colors hover:bg-accent disabled:opacity-60",
                  checked && "border-primary bg-accent",
                )}
              >
                <span className="font-medium">{LANGUAGE_NAMES[option]}</span>
                {checked && <Check className="size-4 text-primary" />}
              </button>
            )
          })}
        </div>
      ) : (
        <Skeleton className="h-32 w-full" />
      )}
    </div>
  )
}
