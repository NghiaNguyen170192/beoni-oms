from typing import Annotated

from fastapi import Depends

from app.api.deps import SessionDep
from app.modules.settings.models import BusinessSettings
from app.modules.settings.service import get_settings


def get_business_settings(session: SessionDep) -> BusinessSettings:
    return get_settings(session)


# FastAPI caches dependencies per request, so settings are read once per request.
BusinessSettingsDep = Annotated[BusinessSettings, Depends(get_business_settings)]
