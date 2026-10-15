import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useEffect } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import {
  type InventoryCategoryPublic,
  type InventoryItemPublic,
  InventoryService,
} from "@/client"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { LoadingButton } from "@/components/ui/loading-button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import useCustomToast from "@/hooks/useCustomToast"
import { t as translate, useI18n } from "@/i18n"
import { ITEM_TYPE_LABELS, ITEM_TYPES, UNIT_LABELS, UNITS } from "@/lib/labels"
import { handleError } from "@/utils"
import { editableQuantity } from "./queries"

const QUANTITY = /^\d+(\.\d{1,4})?$/

const tooLong = (max: number) => ({
  error: () => translate("inventory.validation.tooLong", { max }),
})

const formSchema = z
  .object({
    name: z
      .string()
      .trim()
      .min(1, {
        error: () => translate("inventory.validation.nameRequired"),
      })
      .max(255, tooLong(255)),
    category_id: z.string().min(1, {
      error: () => translate("inventory.validation.categoryRequired"),
    }),
    item_type: z.enum(ITEM_TYPES),
    base_unit: z.enum(UNITS),
    purchase_unit: z.enum(UNITS),
    conversion_factor: z
      .string()
      .trim()
      .regex(QUANTITY, {
        error: () => translate("inventory.validation.upTo4Decimals"),
      })
      .refine((value) => Number(value) > 0, {
        error: () => translate("inventory.validation.greaterThanZero"),
      }),
    min_stock: z
      .string()
      .trim()
      .regex(QUANTITY, {
        error: () => translate("inventory.validation.upTo4Decimals"),
      }),
    barcode: z.string().trim().max(64, tooLong(64)),
    is_active: z.boolean(),
  })
  .refine(
    (data) =>
      data.purchase_unit !== data.base_unit ||
      Number(data.conversion_factor) === 1,
    {
      error: () => translate("inventory.validation.conversionMustBeOne"),
      path: ["conversion_factor"],
    },
  )

type FormData = z.infer<typeof formSchema>

function toFormValues(item: InventoryItemPublic | undefined): FormData {
  return {
    name: item?.name ?? "",
    category_id: item?.category_id ?? "",
    item_type: item?.item_type ?? "ingredient",
    base_unit: item?.base_unit ?? "g",
    purchase_unit: item?.purchase_unit ?? "g",
    conversion_factor: item ? editableQuantity(item.conversion_factor) : "1",
    min_stock: item ? editableQuantity(item.min_stock) : "0",
    barcode: item?.barcode ?? "",
    is_active: item?.is_active ?? true,
  }
}

interface InventoryItemDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  categories: InventoryCategoryPublic[]
  item?: InventoryItemPublic
}

export function InventoryItemDialog({
  open,
  onOpenChange,
  categories,
  item,
}: InventoryItemDialogProps) {
  const { t } = useI18n()
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const isEdit = item !== undefined

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    defaultValues: toFormValues(item),
  })

  const itemId = item?.id
  // biome-ignore lint/correctness/useExhaustiveDependencies: reset only when a different item opens
  useEffect(() => {
    if (open) form.reset(toFormValues(item))
  }, [open, itemId, form])

  const save = useMutation({
    mutationFn: (data: FormData) => {
      const body = { ...data, barcode: data.barcode || null }
      return item
        ? InventoryService.updateItem({ itemId: item.id, requestBody: body })
        : InventoryService.createItem({ requestBody: body })
    },
    onSuccess: () => {
      showSuccessToast(
        isEdit ? t("inventory.itemUpdated") : t("inventory.itemCreated"),
      )
      onOpenChange(false)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () =>
      queryClient.invalidateQueries({ queryKey: ["inventoryItems"] }),
  })

  const unitSelect = (name: "base_unit" | "purchase_unit", label: string) => (
    <FormField
      control={form.control}
      name={name}
      render={({ field }) => (
        <FormItem>
          <FormLabel>{label}</FormLabel>
          <Select value={field.value} onValueChange={field.onChange}>
            <FormControl>
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
            </FormControl>
            <SelectContent>
              {UNITS.map((unit) => (
                <SelectItem key={unit} value={unit}>
                  {t(UNIT_LABELS[unit])}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <FormMessage />
        </FormItem>
      )}
    />
  )

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {isEdit ? t("inventory.editItem") : t("inventory.addItem")}
          </DialogTitle>
          <DialogDescription>
            {t("inventory.dialog.description")}
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit((data) => save.mutate(data))}>
            <div className="grid gap-4 py-4 sm:grid-cols-2">
              {item && (
                <div className="grid gap-2">
                  <Label htmlFor="inventory-item-sku">
                    {t("inventory.field.sku")}
                  </Label>
                  <Input id="inventory-item-sku" value={item.sku} readOnly />
                </div>
              )}
              <FormField
                control={form.control}
                name="barcode"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t("inventory.field.barcode")}</FormLabel>
                    <FormControl>
                      <Input {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem className="sm:col-span-2">
                    <FormLabel>{t("inventory.field.name")}</FormLabel>
                    <FormControl>
                      <Input {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="category_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t("inventory.field.category")}</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue
                            placeholder={t(
                              "inventory.field.categoryPlaceholder",
                            )}
                          />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {categories.map((category) => (
                          <SelectItem key={category.id} value={category.id}>
                            {category.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="item_type"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t("inventory.field.itemType")}</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {ITEM_TYPES.map((type) => (
                          <SelectItem key={type} value={type}>
                            {t(ITEM_TYPE_LABELS[type])}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
              {unitSelect("base_unit", t("inventory.field.baseUnit"))}
              {unitSelect("purchase_unit", t("inventory.field.purchaseUnit"))}
              <FormField
                control={form.control}
                name="conversion_factor"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      {t("inventory.field.conversionFactor")}
                    </FormLabel>
                    <FormControl>
                      <Input inputMode="decimal" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="min_stock"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t("inventory.field.minStock")}</FormLabel>
                    <FormControl>
                      <Input inputMode="decimal" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="is_active"
                render={({ field }) => (
                  <FormItem className="flex items-center gap-3 space-y-0">
                    <FormControl>
                      <Checkbox
                        checked={field.value}
                        onCheckedChange={field.onChange}
                      />
                    </FormControl>
                    <FormLabel className="font-normal">
                      {t("inventory.status.active")}
                    </FormLabel>
                  </FormItem>
                )}
              />
            </div>
            <DialogFooter>
              <DialogClose asChild>
                <Button variant="outline" disabled={save.isPending}>
                  {t("common.cancel")}
                </Button>
              </DialogClose>
              <LoadingButton type="submit" loading={save.isPending}>
                {t("common.save")}
              </LoadingButton>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
