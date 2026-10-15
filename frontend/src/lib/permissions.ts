import { redirect } from "@tanstack/react-router"

import {
  type Permission,
  type Role,
  type UserMePublic,
  UsersService,
} from "@/client"
import type { MessageKey } from "@/i18n"

export const ROLES = [
  "owner",
  "manager",
  "cashier",
  "inventory_staff",
  "accountant",
] as const satisfies readonly Role[]

/** Message keys; translate with `t(ROLE_LABELS[role])`. */
export const ROLE_LABELS = {
  owner: "role.owner",
  manager: "role.manager",
  cashier: "role.cashier",
  inventory_staff: "role.inventory_staff",
  accountant: "role.accountant",
} as const satisfies Record<Role, MessageKey>

/** A person's display name: full name, falling back to email. */
export function displayName(
  name: string | null | undefined,
  email: string | null | undefined,
): string {
  return name?.trim() || email || "—"
}

export function hasPermission(
  user: UserMePublic | null | undefined,
  permission: Permission,
): boolean {
  return user?.permissions.includes(permission) ?? false
}

export function hasAnyPermission(
  user: UserMePublic | null | undefined,
  permissions: readonly Permission[],
): boolean {
  return permissions.some((permission) => hasPermission(user, permission))
}

/** `beforeLoad` guard: redirect home unless the user has any of `permissions`. */
export function requirePermission(...permissions: Permission[]) {
  return async () => {
    const user = await UsersService.readUserMe()
    if (!hasAnyPermission(user, permissions)) {
      throw redirect({ to: "/" })
    }
  }
}
