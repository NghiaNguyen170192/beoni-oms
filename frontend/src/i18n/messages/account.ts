export const en = {
  "account.dashboard.pageTitle": "Dashboard - FastAPI Template",
  "account.dashboard.greeting": "Hi, {name} 👋",
  "account.dashboard.welcome": "Welcome back, nice to see you again!!!",

  "account.settings.pageTitle": "Settings - FastAPI Template",
  "account.settings.description":
    "Manage your account settings and preferences",
  "account.tabs.profile": "My profile",
  "account.tabs.password": "Password",
  "account.tabs.business": "Business",
  "account.tabs.dangerZone": "Danger zone",

  "account.profile.title": "User Information",
  "account.profile.fullName": "Full name",
  "account.profile.fullNameMax": "Full name must be at most 30 characters",
  "account.profile.updated": "User updated successfully",

  "account.password.title": "Change Password",
  "account.password.current": "Current Password",
  "account.password.submit": "Update Password",

  "account.delete.title": "Delete Account",
  "account.delete.description":
    "Permanently delete your account and all associated data.",
  "account.delete.success": "Your account has been successfully deleted",
  "account.delete.confirmTitle": "Confirmation Required",
  "account.delete.confirmDescription":
    "All your account data will be {deleted} If you are sure, please click {confirm} to proceed. This action cannot be undone.",
  "account.delete.confirmWord": '"Confirm"',

  "account.business.title": "Business",
  "account.business.name": "Business name",
  "account.business.nameRequired": "Business name is required",
  "account.business.nameMax": "Business name must be at most 255 characters",
  "account.business.currency": "Currency",
  "account.business.currencyHint": "Only {currencies} is supported.",
  "account.business.timezone": "Timezone",
  "account.business.timezoneRequired": "Timezone is required",
  "account.business.timezoneHint": "IANA name, e.g. Asia/Ho_Chi_Minh",
  "account.business.taxRate": "Tax rate (%)",
  "account.business.taxRateFormat":
    "Tax rate must be a number with at most 2 decimals",
  "account.business.taxRateRange": "Tax rate must be between 0 and 100",
  "account.business.taxRateHint":
    "Included in menu prices; applies to new orders.",
  "account.business.allowNegativeStock": "Allow negative stock",
  "account.business.preview": "Preview:",
  "account.business.updated": "Business settings updated",
  "account.business.ownerOnly": "Only the owner can change business settings.",
} as const

export const vi: Record<keyof typeof en, string> = {
  "account.dashboard.pageTitle": "Tổng quan - FastAPI Template",
  "account.dashboard.greeting": "Xin chào, {name} 👋",
  "account.dashboard.welcome": "Chào mừng bạn quay lại!",

  "account.settings.pageTitle": "Cài đặt - FastAPI Template",
  "account.settings.description":
    "Quản lý thông tin tài khoản và tùy chọn của bạn",
  "account.tabs.profile": "Hồ sơ của tôi",
  "account.tabs.password": "Mật khẩu",
  "account.tabs.business": "Cửa hàng",
  "account.tabs.dangerZone": "Vùng nguy hiểm",

  "account.profile.title": "Thông tin người dùng",
  "account.profile.fullName": "Họ và tên",
  "account.profile.fullNameMax": "Họ và tên tối đa 30 ký tự",
  "account.profile.updated": "Đã cập nhật thông tin",

  "account.password.title": "Đổi mật khẩu",
  "account.password.current": "Mật khẩu hiện tại",
  "account.password.submit": "Cập nhật mật khẩu",

  "account.delete.title": "Xóa tài khoản",
  "account.delete.description":
    "Xóa vĩnh viễn tài khoản và toàn bộ dữ liệu liên quan.",
  "account.delete.success": "Tài khoản của bạn đã được xóa",
  "account.delete.confirmTitle": "Cần xác nhận",
  "account.delete.confirmDescription":
    "Toàn bộ dữ liệu tài khoản của bạn sẽ bị {deleted} Nếu chắc chắn, hãy nhấn {confirm} để tiếp tục. Thao tác này không thể hoàn tác.",
  "account.delete.confirmWord": "“Xóa”",

  "account.business.title": "Cửa hàng",
  "account.business.name": "Tên cửa hàng",
  "account.business.nameRequired": "Vui lòng nhập tên cửa hàng",
  "account.business.nameMax": "Tên cửa hàng tối đa 255 ký tự",
  "account.business.currency": "Tiền tệ",
  "account.business.currencyHint": "Hiện chỉ hỗ trợ {currencies}.",
  "account.business.timezone": "Múi giờ",
  "account.business.timezoneRequired": "Vui lòng nhập múi giờ",
  "account.business.timezoneHint": "Tên múi giờ IANA, ví dụ Asia/Ho_Chi_Minh",
  "account.business.taxRate": "Thuế suất (%)",
  "account.business.taxRateFormat":
    "Thuế suất phải là số, tối đa 2 chữ số thập phân",
  "account.business.taxRateRange": "Thuế suất phải từ 0 đến 100",
  "account.business.taxRateHint":
    "Đã bao gồm trong giá thực đơn; áp dụng cho đơn hàng mới.",
  "account.business.allowNegativeStock": "Cho phép tồn kho âm",
  "account.business.preview": "Xem trước:",
  "account.business.updated": "Đã cập nhật cài đặt cửa hàng",
  "account.business.ownerOnly":
    "Chỉ chủ cửa hàng mới được thay đổi cài đặt này.",
}
