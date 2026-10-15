import type { MenuCategoryPublic } from "@/client"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useI18n } from "@/i18n"

const ALL = "all"

interface CategoryTabsProps {
  categories: MenuCategoryPublic[]
  value: string | undefined
  onChange: (categoryId: string | undefined) => void
  className?: string
}

export function CategoryTabs({
  categories,
  value,
  onChange,
  className,
}: CategoryTabsProps) {
  const { t } = useI18n()
  return (
    <Tabs
      value={value ?? ALL}
      onValueChange={(next) => onChange(next === ALL ? undefined : next)}
      className={className}
    >
      <TabsList className="h-auto max-w-full flex-wrap justify-start">
        <TabsTrigger value={ALL} className="flex-none px-4">
          {t("common.all")}
        </TabsTrigger>
        {categories.map((category) => (
          <TabsTrigger
            key={category.id}
            value={category.id}
            className="flex-none px-4"
          >
            {category.name}
          </TabsTrigger>
        ))}
      </TabsList>
    </Tabs>
  )
}
