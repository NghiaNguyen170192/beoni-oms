import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { ImageUp } from "lucide-react"
import { useEffect, useRef } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import {
  type ApiError,
  CatalogService,
  type MenuCategoryPublic,
  type MenuItemPublic,
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
import { t, useI18n } from "@/i18n"
import { formatAmountInput, parseAmountInput } from "@/lib/format"
import { PRODUCT_TYPE_LABELS, PRODUCT_TYPES } from "@/lib/labels"
import { mediaUrl } from "@/lib/media"
import { handleError } from "@/utils"
import { editableAmount } from "./queries"

const MAX_IMAGE_BYTES = 2 * 1024 * 1024

const formSchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, { error: () => t("catalog.nameRequired") })
    .max(255, { error: () => t("catalog.nameTooLong") }),
  description: z
    .string()
    .max(1000, { error: () => t("catalog.descriptionTooLong") }),
  category_id: z
    .string()
    .min(1, { error: () => t("catalog.categoryRequired") }),
  price: z
    .string()
    .trim()
    .regex(/^\d+(\.\d{1,2})?$/, {
      error: () => t("catalog.priceInvalid"),
    }),
  product_type: z.enum(PRODUCT_TYPES),
  is_active: z.boolean(),
  is_available: z.boolean(),
})

type FormData = z.infer<typeof formSchema>

interface MenuItemDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  categories: MenuCategoryPublic[]
  /** Edit this item; create a new one when omitted. */
  item?: MenuItemPublic
  defaultCategoryId?: string
}

function toFormValues(
  item: MenuItemPublic | undefined,
  defaultCategoryId: string | undefined,
): FormData {
  return {
    name: item?.name ?? "",
    description: item?.description ?? "",
    category_id: item?.category_id ?? defaultCategoryId ?? "",
    price: item ? editableAmount(item.price) : "",
    product_type: item?.product_type ?? "prepared",
    is_active: item?.is_active ?? true,
    is_available: item?.is_available ?? true,
  }
}

export function MenuItemDialog({
  open,
  onOpenChange,
  categories,
  item,
  defaultCategoryId,
}: MenuItemDialogProps) {
  const { t } = useI18n()
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const fileInput = useRef<HTMLInputElement>(null)
  const isEdit = item !== undefined

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    defaultValues: toFormValues(item, defaultCategoryId),
  })

  // Reset only when a different item opens, so a refetch (e.g. after an image
  // upload) does not discard unsaved edits.
  const itemId = item?.id
  // biome-ignore lint/correctness/useExhaustiveDependencies: see above
  useEffect(() => {
    if (open) {
      form.reset(toFormValues(item, defaultCategoryId))
    }
  }, [open, itemId, defaultCategoryId, form])

  const onError = handleError.bind(showErrorToast)
  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["menuItems"] })

  const save = useMutation({
    mutationFn: (data: FormData) => {
      const body = { ...data, description: data.description || null }
      return item
        ? CatalogService.updateItem({ itemId: item.id, requestBody: body })
        : CatalogService.createItem({ requestBody: body })
    },
    onSuccess: () => {
      showSuccessToast(
        isEdit ? t("catalog.itemUpdated") : t("catalog.itemCreated"),
      )
      onOpenChange(false)
    },
    onError,
    onSettled: invalidate,
  })

  const upload = useMutation({
    mutationFn: (file: File) =>
      CatalogService.uploadItemImage({
        itemId: item!.id,
        formData: { file },
      }),
    onSuccess: () => showSuccessToast(t("catalog.imageUploaded")),
    onError: (err: ApiError) => onError(err),
    onSettled: invalidate,
  })

  const onFileChosen = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ""
    if (!file) return
    if (file.size > MAX_IMAGE_BYTES) {
      showErrorToast(t("catalog.imageTooLarge"))
      return
    }
    upload.mutate(file)
  }

  const imageSrc = mediaUrl(item?.image_path)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {isEdit ? t("catalog.editItemTitle") : t("catalog.addItemTitle")}
          </DialogTitle>
          <DialogDescription>
            {t("catalog.itemDialogDescription")}
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit((data) => save.mutate(data))}>
            <div className="grid gap-4 py-4 sm:grid-cols-2">
              {isEdit && (
                <div className="grid gap-2">
                  <Label htmlFor="menu-item-code">{t("catalog.code")}</Label>
                  <Input id="menu-item-code" value={item.code} disabled />
                </div>
              )}
              <FormField
                control={form.control}
                name="price"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t("catalog.price")}</FormLabel>
                    <FormControl>
                      <Input
                        inputMode="decimal"
                        placeholder="0"
                        {...field}
                        value={formatAmountInput(field.value)}
                        onChange={(event) =>
                          field.onChange(parseAmountInput(event.target.value))
                        }
                      />
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
                    <FormLabel>{t("common.name")}</FormLabel>
                    <FormControl>
                      <Input {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="description"
                render={({ field }) => (
                  <FormItem className="sm:col-span-2">
                    <FormLabel>{t("catalog.description")}</FormLabel>
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
                    <FormLabel>{t("catalog.category")}</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue
                            placeholder={t("catalog.chooseCategory")}
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
                name="product_type"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t("catalog.productType")}</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {PRODUCT_TYPES.map((type) => (
                          <SelectItem key={type} value={type}>
                            {t(PRODUCT_TYPE_LABELS[type])}
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
                      {t("catalog.active")}
                    </FormLabel>
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="is_available"
                render={({ field }) => (
                  <FormItem className="flex items-center gap-3 space-y-0">
                    <FormControl>
                      <Checkbox
                        checked={field.value}
                        onCheckedChange={field.onChange}
                      />
                    </FormControl>
                    <FormLabel className="font-normal">
                      {t("catalog.available")}
                    </FormLabel>
                  </FormItem>
                )}
              />

              {isEdit && (
                <div className="flex items-center gap-4 sm:col-span-2">
                  {imageSrc ? (
                    <img
                      src={imageSrc}
                      alt={item.name}
                      className="size-16 rounded-md object-cover border"
                    />
                  ) : (
                    <div className="size-16 rounded-md border bg-muted" />
                  )}
                  <input
                    ref={fileInput}
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    className="hidden"
                    aria-label={t("catalog.imageFile")}
                    onChange={onFileChosen}
                  />
                  <LoadingButton
                    type="button"
                    variant="outline"
                    loading={upload.isPending}
                    onClick={() => fileInput.current?.click()}
                  >
                    <ImageUp className="mr-2" />
                    {t("catalog.uploadImage")}
                  </LoadingButton>
                  <span className="text-xs text-muted-foreground">
                    {t("catalog.imageHint")}
                  </span>
                </div>
              )}
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
