from app.core.errors import Conflict, NotFound


class AccountNotFound(NotFound):
    code = "account_not_found"


class ExpenseNotFound(NotFound):
    code = "expense_not_found"


class ExpenseCategoryNotFound(NotFound):
    code = "expense_category_not_found"


class ExpenseCategoryInUse(Conflict):
    code = "expense_category_in_use"


class ExpenseAlreadyPaid(Conflict):
    code = "expense_already_paid"


class ExpenseAlreadyReversed(Conflict):
    code = "expense_already_reversed"


class PaidExpenseNeedsAccount(Conflict):
    code = "paid_expense_needs_account"


class SupplierPaymentNotFound(NotFound):
    code = "supplier_payment_not_found"


class SupplierPaymentAlreadyReversed(Conflict):
    code = "supplier_payment_already_reversed"


class AllocationMismatch(Conflict):
    code = "allocation_mismatch"


class OverAllocation(Conflict):
    code = "over_allocation"


class AdjustmentAlreadyReversed(Conflict):
    code = "adjustment_already_reversed"


class AdjustmentNotFound(NotFound):
    code = "adjustment_not_found"
