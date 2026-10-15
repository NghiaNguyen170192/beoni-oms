from app.core.errors import Conflict, Invalid, NotFound


class OrderNotFound(NotFound):
    default_detail = "Order not found"


class OrderLineNotFound(NotFound):
    default_detail = "Order line not found"


class OrderNotEditable(Conflict):
    default_detail = "Only draft or confirmed orders can be changed"


class EmptyOrder(Invalid):
    default_detail = "An order needs at least one line"


class InvalidOrderChange(Invalid):
    default_detail = "Invalid order change"


class ReceiptUnavailable(Conflict):
    default_detail = "Receipts are available for confirmed and later orders"
