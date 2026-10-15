from app.core.errors import Conflict, Invalid, NotFound


class SupplierNotFound(NotFound):
    default_detail = "Supplier not found"


class SupplierCodeTaken(Conflict):
    default_detail = "A supplier with this code already exists"


class SupplierHasReceipts(Conflict):
    default_detail = "Supplier has receipts; deactivate it instead"


class SupplierInactive(Invalid):
    default_detail = "Supplier is inactive"


class ReceiptNotFound(NotFound):
    default_detail = "Stock receipt not found"


class ReceiptReferenceTaken(Conflict):
    default_detail = "A receipt with this reference already exists"


class ReceiptNotDraft(Conflict):
    default_detail = "Only draft receipts can be changed"


class ReceiptNotPosted(Conflict):
    default_detail = "Only a posted receipt can be reversed"


class ReceiptAlreadyPosted(Conflict):
    default_detail = "Receipt is already posted"


class ReceiptHasPayments(Conflict):
    default_detail = "Receipt has applied payments and cannot be reversed"


class ReceiptHasNoLines(Invalid):
    default_detail = "Receipt must have at least one line"
