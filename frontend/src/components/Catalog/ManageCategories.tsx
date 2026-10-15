import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { ArrowDown, ArrowUp, FolderCog, Plus } from "lucide-react"
import { type FormEvent, useState } from "react"

import { CatalogService, type MenuCategoryPublic } from "@/client"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { useI18n } from "@/i18n"
import { handleError } from "@/utils"
import { menuCategoriesQueryOptions } from "./queries"

function CategoryRow({
  category,
  isFirst,
  isLast,
  onMove,
}: {
  category: MenuCategoryPublic
  isFirst: boolean
  isLast: boolean
  onMove: (direction: -1 | 1) => void
}) {
  const { t } = useI18n()
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [name, setName] = useState(category.name)

  const update = useMutation({
    mutationFn: (body: { name?: string; is_active?: boolean }) =>
      CatalogService.updateCategory({
        categoryId: category.id,
        requestBody: body,
      }),
    onSuccess: () => showSuccessToast(t("catalog.categoryUpdated")),
    onError: handleError.bind(showErrorToast),
    onSettled: () =>
      queryClient.invalidateQueries({ queryKey: ["menuCategories"] }),
  })

  const rename = (event: FormEvent) => {
    event.preventDefault()
    if (name.trim() && name.trim() !== category.name) {
      update.mutate({ name: name.trim() })
    }
  }

  return (
    <form onSubmit={rename} className="flex items-center gap-2">
      <Input
        aria-label={t("catalog.categoryNameLabel", { name: category.name })}
        value={name}
        onChange={(e) => setName(e.target.value)}
        className="flex-1"
      />
      {!category.is_active && (
        <Badge variant="secondary">{t("common.inactive")}</Badge>
      )}
      <Button
        type="button"
        variant="ghost"
        size="icon"
        aria-label={t("catalog.moveUp")}
        disabled={isFirst}
        onClick={() => onMove(-1)}
      >
        <ArrowUp />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        aria-label={t("catalog.moveDown")}
        disabled={isLast}
        onClick={() => onMove(1)}
      >
        <ArrowDown />
      </Button>
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={update.isPending}
        onClick={() => update.mutate({ is_active: !category.is_active })}
      >
        {category.is_active ? t("catalog.deactivate") : t("catalog.activate")}
      </Button>
    </form>
  )
}

export function ManageCategories() {
  const { t } = useI18n()
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [newName, setNewName] = useState("")
  const { data } = useQuery(menuCategoriesQueryOptions(true))
  const categories = data?.data ?? []

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["menuCategories"] })
  const onError = handleError.bind(showErrorToast)

  const create = useMutation({
    mutationFn: (name: string) =>
      CatalogService.createCategory({
        requestBody: { name, sort_order: categories.length },
      }),
    onSuccess: () => {
      showSuccessToast(t("catalog.categoryCreated"))
      setNewName("")
    },
    onError,
    onSettled: invalidate,
  })

  const reorder = useMutation({
    mutationFn: (ids: string[]) =>
      CatalogService.reorderCategories({ requestBody: { category_ids: ids } }),
    onError,
    onSettled: invalidate,
  })

  const move = (index: number, direction: -1 | 1) => {
    const ids = categories.map((category) => category.id)
    const target = index + direction
    ;[ids[index], ids[target]] = [ids[target], ids[index]]
    reorder.mutate(ids)
  }

  const submitNew = (event: FormEvent) => {
    event.preventDefault()
    if (newName.trim()) create.mutate(newName.trim())
  }

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="outline">
          <FolderCog className="mr-2" />
          {t("catalog.categories")}
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{t("catalog.categoriesTitle")}</DialogTitle>
          <DialogDescription>
            {t("catalog.categoriesDescription")}
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-2 py-2">
          {categories.map((category, index) => (
            <CategoryRow
              key={`${category.id}-${category.name}`}
              category={category}
              isFirst={index === 0}
              isLast={index === categories.length - 1}
              onMove={(direction) => move(index, direction)}
            />
          ))}
        </div>
        <form onSubmit={submitNew} className="flex items-center gap-2">
          <Input
            aria-label={t("catalog.newCategoryLabel")}
            placeholder={t("catalog.newCategoryPlaceholder")}
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
          />
          <LoadingButton type="submit" loading={create.isPending}>
            <Plus className="mr-2" />
            {t("common.add")}
          </LoadingButton>
        </form>
      </DialogContent>
    </Dialog>
  )
}
