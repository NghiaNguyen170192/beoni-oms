from app.core.errors import Conflict, Invalid, NotFound


class PaymentMethodNotFound(NotFound):
    default_detail = "Payment method not found"


class PaymentMethodNameTaken(Conflict):
    default_detail = "A payment method with this name already exists"


class PaymentMethodInactive(Invalid):
    default_detail = "Payment method is inactive"


class PaymentNotFound(NotFound):
    default_detail = "Payment not found"


class PaymentNotAllowed(Conflict):
    default_detail = "Payments can be recorded on draft, confirmed, or paid orders"


class Overpayment(Conflict):
    default_detail = "Payment would exceed the order total"


class PaymentShort(Conflict):
    default_detail = "Order is not fully paid"


class PaymentAlreadyVoided(Conflict):
    default_detail = "Payment is already voided"


class VoidNotAllowed(Conflict):
    default_detail = "Payments on a completed order cannot be voided; record a refund"


class RefundNotAllowed(Conflict):
    default_detail = "Refunds are recorded on completed orders"


class OverRefund(Conflict):
    default_detail = "Refund would exceed the amount paid"
