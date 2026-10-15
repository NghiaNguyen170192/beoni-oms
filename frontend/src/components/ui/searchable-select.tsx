import { useEffect, useRef, useState } from "react"

import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useI18n } from "@/i18n"
import { cn } from "@/lib/utils"

export type SearchableSelectOption = {
  value: string
  label: string
}

/** Select whose list filters as the user types. Each instance keeps its own query. */
export function SearchableSelect({
  value,
  onValueChange,
  options,
  placeholder,
  searchLabel,
  emptyLabel,
  "aria-label": ariaLabel,
  className,
  disabled,
}: {
  value: string
  onValueChange: (value: string) => void
  options: SearchableSelectOption[]
  placeholder?: string
  searchLabel?: string
  emptyLabel?: string
  "aria-label"?: string
  className?: string
  disabled?: boolean
}) {
  const { t } = useI18n()
  const searchRef = useRef<HTMLInputElement>(null)
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")
  const needle = query.trim().toLowerCase()
  const visible = needle
    ? options.filter((option) => option.label.toLowerCase().includes(needle))
    : options
  const selected = options.find((option) => option.value === value)
  const keepSelected =
    selected != null && !visible.some((option) => option.value === selected.value)
  const searchText = searchLabel ?? t("common.search")

  useEffect(() => {
    if (!open) return
    const frame = requestAnimationFrame(() => searchRef.current?.focus())
    return () => cancelAnimationFrame(frame)
  }, [open])

  return (
    <Select
      value={value || undefined}
      disabled={disabled}
      open={open}
      onValueChange={onValueChange}
      onOpenChange={(next) => {
        setOpen(next)
        if (!next) setQuery("")
      }}
    >
      <SelectTrigger aria-label={ariaLabel} className={cn("w-full min-w-0", className)}>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent
        header={
          <div
            className="shrink-0 border-b bg-popover p-1"
            onPointerDown={(event) => event.stopPropagation()}
          >
            <Input
              ref={searchRef}
              value={query}
              aria-label={searchText}
              placeholder={searchText}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => event.stopPropagation()}
            />
          </div>
        }
      >
        {keepSelected && (
          <SelectItem value={selected.value} className="hidden">
            {selected.label}
          </SelectItem>
        )}
        {visible.length === 0 ? (
          <p className="px-2 py-1.5 text-sm text-muted-foreground">
            {emptyLabel ?? t("common.noResults")}
          </p>
        ) : (
          visible.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))
        )}
      </SelectContent>
    </Select>
  )
}
