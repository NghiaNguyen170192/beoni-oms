from app.core.errors import Invalid


class RangeTooLong(Invalid):
    default_detail = "Date range cannot exceed 366 days"
