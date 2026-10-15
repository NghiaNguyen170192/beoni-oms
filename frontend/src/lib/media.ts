import { OpenAPI } from "@/client"

export function mediaUrl(path: string | null | undefined): string | null {
  return path ? `${OpenAPI.BASE}/media/${path}` : null
}
