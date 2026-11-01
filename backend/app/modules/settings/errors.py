from app.core.errors import NotFound


class OrderFeeTypeNotFound(NotFound):
    default_detail = "Order fee type not found"
