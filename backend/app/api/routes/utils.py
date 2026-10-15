import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic.networks import EmailStr
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import select

from app.api.deps import SessionDep
from app.models import Message
from app.modules.identity.dependencies import require_permission
from app.modules.identity.permissions import Permission
from app.utils import generate_test_email, send_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/utils", tags=["utils"])


@router.post(
    "/test-email/",
    dependencies=[Depends(require_permission(Permission.SETTINGS_MANAGE))],
    status_code=201,
)
def test_email(email_to: EmailStr) -> Message:
    """
    Test emails.
    """
    email_data = generate_test_email(email_to=email_to)
    send_email(
        email_to=email_to,
        subject=email_data.subject,
        html_content=email_data.html_content,
    )
    return Message(message="Test email sent")


@router.get("/health-check/")
async def health_check() -> bool:
    """
    Liveness: the process is up. Does not touch the database.
    """
    return True


@router.get("/ready/", responses={503: {"description": "Database unavailable"}})
def readiness_check(session: SessionDep) -> bool:
    """
    Readiness: the database answers `SELECT 1`.
    """
    try:
        session.exec(select(1))
    except SQLAlchemyError:
        logger.warning("Readiness check failed: database unavailable", exc_info=True)
        raise HTTPException(status_code=503, detail="Database unavailable")
    return True
