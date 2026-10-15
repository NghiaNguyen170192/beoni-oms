import {
  Banknote,
  ChefHat,
  Coffee,
  History,
  Home,
  Landmark,
  Languages,
  Package,
  ReceiptText,
  Shield,
  ShoppingCart,
  SlidersHorizontal,
  Truck,
  Users,
  Wallet,
  Warehouse,
} from "lucide-react"

import type { Permission, UserMePublic } from "@/client"
import { SidebarAppearance } from "@/components/Common/Appearance"
import { Logo } from "@/components/Common/Logo"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
} from "@/components/ui/sidebar"
import useAuth from "@/hooks/useAuth"
import { type MessageKey, useI18n } from "@/i18n"
import { hasAnyPermission } from "@/lib/permissions"
import { type Item, Main } from "./Main"
import { User } from "./User"

/** Shown when the user has any of `permissions` (or always when omitted). */
type NavItem = Omit<Item, "title" | "children"> & {
  title: MessageKey
  permissions?: Permission[]
  children?: NavItem[]
}

const navItems: NavItem[] = [
  { icon: Home, title: "nav.dashboard", path: "/" },
  {
    icon: ShoppingCart,
    title: "nav.pos",
    path: "/pos",
    permissions: ["ordering:create"],
  },
  {
    icon: ReceiptText,
    title: "nav.orders",
    path: "/orders",
    permissions: ["ordering:view_own", "ordering:view_all"],
  },
  {
    icon: Banknote,
    title: "nav.payments",
    path: "/payments",
    permissions: ["payments:read"],
  },
  {
    icon: Coffee,
    title: "nav.menu",
    path: "/menu",
    permissions: ["catalog:view"],
  },
  {
    icon: Package,
    title: "nav.inventory",
    path: "/inventory",
    permissions: ["inventory:view"],
  },
  {
    icon: SlidersHorizontal,
    title: "nav.stockAdjustments",
    path: "/stock-adjustments",
    permissions: ["inventory:view"],
  },
  {
    icon: Truck,
    title: "nav.suppliers",
    path: "/suppliers",
    permissions: ["purchasing:read"],
  },
  {
    icon: Warehouse,
    title: "nav.stockReceipts",
    path: "/stock-receipts",
    permissions: ["purchasing:read"],
  },
  {
    icon: ChefHat,
    title: "nav.recipes",
    path: "/recipes",
    permissions: ["recipes:read"],
  },
  {
    icon: Wallet,
    title: "nav.expenses",
    path: "/expenses",
    permissions: ["expenses:read"],
  },
  {
    icon: Landmark,
    title: "nav.cash",
    path: "/cash",
    permissions: ["cash:view"],
  },
  {
    icon: Shield,
    title: "nav.admin",
    path: "/admin",
    children: [
      {
        icon: Users,
        title: "nav.users",
        path: "/admin",
        permissions: ["users:manage"],
      },
      {
        icon: History,
        title: "nav.auditLog",
        path: "/admin/audit-log",
        permissions: ["audit:read"],
      },
      {
        icon: Languages,
        title: "nav.language",
        path: "/admin/language",
        permissions: ["settings:manage"],
      },
    ],
  },
]

/** Permitted items, translated; a group links to its first permitted child. */
function visibleItems(
  items: NavItem[],
  user: UserMePublic | null | undefined,
  t: (key: MessageKey) => string,
): Item[] {
  return items.flatMap((item): Item[] => {
    if (item.permissions && !hasAnyPermission(user, item.permissions)) {
      return []
    }
    if (!item.children) {
      return [{ icon: item.icon, title: t(item.title), path: item.path }]
    }
    const children = visibleItems(item.children, user, t)
    if (children.length === 0) return []
    return [
      {
        icon: item.icon,
        title: t(item.title),
        path: children[0].path,
        children,
      },
    ]
  })
}

export function AppSidebar() {
  const { user: currentUser } = useAuth()
  const { t } = useI18n()

  const items = visibleItems(navItems, currentUser, t)

  return (
    <Sidebar collapsible="icon" className="print:hidden">
      <SidebarHeader className="px-4 py-6 group-data-[collapsible=icon]:px-0 group-data-[collapsible=icon]:items-center">
        <Logo variant="responsive" />
      </SidebarHeader>
      <SidebarContent>
        <Main items={items} />
      </SidebarContent>
      <SidebarFooter>
        <SidebarAppearance />
        <User user={currentUser} />
      </SidebarFooter>
    </Sidebar>
  )
}

export default AppSidebar
