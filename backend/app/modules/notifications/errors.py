from app.core.errors import NotFound


class NotificationNotFound(NotFound):
    default_detail = "Notification not found"
