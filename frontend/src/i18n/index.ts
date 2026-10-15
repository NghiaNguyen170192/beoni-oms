import { useSyncExternalStore } from "react"

import type { Language } from "@/client"
import * as account from "./messages/account"
import * as accounting from "./messages/accounting"
import * as admin from "./messages/admin"
import * as audit from "./messages/audit"
import * as auth from "./messages/auth"
import * as catalog from "./messages/catalog"
import * as common from "./messages/common"
import * as inventory from "./messages/inventory"
import * as ordering from "./messages/ordering"
import * as payments from "./messages/payments"
import * as purchasing from "./messages/purchasing"
import * as recipes from "./messages/recipes"

export type { Language }

const en = {
  ...common.en,
  ...auth.en,
  ...account.en,
  ...admin.en,
  ...audit.en,
  ...catalog.en,
  ...inventory.en,
  ...ordering.en,
  ...purchasing.en,
  ...payments.en,
  ...recipes.en,
  ...accounting.en,
}

export type MessageKey = keyof typeof en
export type MessageParams = Record<string, string | number>

const vi: Record<MessageKey, string> = {
  ...common.vi,
  ...auth.vi,
  ...account.vi,
  ...admin.vi,
  ...audit.vi,
  ...catalog.vi,
  ...inventory.vi,
  ...ordering.vi,
  ...purchasing.vi,
  ...payments.vi,
  ...recipes.vi,
  ...accounting.vi,
}

const dictionaries: Record<Language, Record<MessageKey, string>> = { en, vi }

export const LANGUAGES = ["en", "vi"] as const satisfies readonly Language[]

/** Each language is named in itself so it is recognisable whatever is active. */
export const LANGUAGE_NAMES: Record<Language, string> = {
  en: "English",
  vi: "Tiếng Việt",
}

// The business language is cached so login screens render in it before the
// settings can be fetched.
const STORAGE_KEY = "language"
const listeners = new Set<() => void>()

function isLanguage(value: unknown): value is Language {
  return LANGUAGES.includes(value as Language)
}

function readStored(): Language {
  const stored = localStorage.getItem(STORAGE_KEY)
  return isLanguage(stored) ? stored : "en"
}

let current: Language = readStored()
document.documentElement.lang = current

export function getLanguage(): Language {
  return current
}

export function setLanguage(language: Language): void {
  if (language === current) return
  current = language
  localStorage.setItem(STORAGE_KEY, language)
  document.documentElement.lang = language
  for (const listener of listeners) listener()
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

/**
 * Translate `key` into the active language, replacing `{name}` placeholders.
 * Outside React this reads the current language; components should call
 * `useI18n()` so they re-render when it changes.
 */
export function t(key: MessageKey, params?: MessageParams): string {
  const template = dictionaries[current][key]
  if (!params) return template
  return template.replace(/\{(\w+)\}/g, (match, name: string) =>
    name in params ? String(params[name]) : match,
  )
}

export function useI18n() {
  const language = useSyncExternalStore(subscribe, getLanguage)
  return { language, t }
}
