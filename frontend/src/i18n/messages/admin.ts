export const en = {
  "admin.pageTitle": "Admin - FastAPI Template",
  "admin.description": "Manage user accounts and permissions",

  "admin.columns.you": "You",
  "admin.columns.superuser": "Superuser",

  "admin.form.fullNamePlaceholder": "Full name",
  "admin.form.setPassword": "Set Password",
  "admin.form.confirmPasswordRequired": "Please confirm your password",
  "admin.form.isSuperuser": "Is superuser?",
  "admin.form.isActive": "Is active?",

  "admin.addUser.button": "Add User",
  "admin.addUser.title": "Add User",
  "admin.addUser.description":
    "Fill in the form below to add a new user to the system.",
  "admin.addUser.success": "User created successfully",

  "admin.editUser.menuItem": "Edit User",
  "admin.editUser.title": "Edit User",
  "admin.editUser.description": "Update the user details below.",
  "admin.editUser.success": "User updated successfully",

  "admin.deleteUser.menuItem": "Delete User",
  "admin.deleteUser.title": "Delete User",
  "admin.deleteUser.description":
    "All items associated with this user will also be {deleted} Are you sure? You will not be able to undo this action.",
  "admin.deleteUser.success": "The user was deleted successfully",
} as const

export const vi: Record<keyof typeof en, string> = {
  "admin.pageTitle": "Quản trị - FastAPI Template",
  "admin.description": "Quản lý tài khoản và phân quyền người dùng",

  "admin.columns.you": "Bạn",
  "admin.columns.superuser": "Siêu quản trị",

  "admin.form.fullNamePlaceholder": "Họ và tên",
  "admin.form.setPassword": "Đặt mật khẩu",
  "admin.form.confirmPasswordRequired": "Vui lòng xác nhận mật khẩu",
  "admin.form.isSuperuser": "Siêu quản trị?",
  "admin.form.isActive": "Đang hoạt động?",

  "admin.addUser.button": "Thêm người dùng",
  "admin.addUser.title": "Thêm người dùng",
  "admin.addUser.description":
    "Điền thông tin bên dưới để thêm người dùng mới vào hệ thống.",
  "admin.addUser.success": "Đã tạo người dùng",

  "admin.editUser.menuItem": "Sửa người dùng",
  "admin.editUser.title": "Sửa người dùng",
  "admin.editUser.description": "Cập nhật thông tin người dùng bên dưới.",
  "admin.editUser.success": "Đã cập nhật người dùng",

  "admin.deleteUser.menuItem": "Xóa người dùng",
  "admin.deleteUser.title": "Xóa người dùng",
  "admin.deleteUser.description":
    "Toàn bộ dữ liệu liên quan đến người dùng này cũng sẽ bị {deleted} Bạn có chắc chắn? Thao tác này không thể hoàn tác.",
  "admin.deleteUser.success": "Đã xóa người dùng",
}
