"""Imports every domain module's tables so they register on SQLModel.metadata.

`app.models` imports this module; Alembic autogenerate and `init_db` rely on it.
Add one import per new domain module.
"""

from app.modules.accounting import models as accounting_models  # noqa: F401
from app.modules.audit import models as audit_models  # noqa: F401
from app.modules.catalog import models as catalog_models  # noqa: F401
from app.modules.idempotency import models as idempotency_models  # noqa: F401
from app.modules.inventory import models as inventory_models  # noqa: F401
from app.modules.ordering import models as ordering_models  # noqa: F401
from app.modules.payments import models as payments_models  # noqa: F401
from app.modules.purchasing import models as purchasing_models  # noqa: F401
from app.modules.recipes import models as recipes_models  # noqa: F401
from app.modules.settings import models as settings_models  # noqa: F401
