import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.api.deps import SessionDep
from app.models import User
from app.modules.identity.dependencies import require_permission
from app.modules.identity.permissions import Permission
from app.modules.recipes import service
from app.modules.recipes.schemas import (
    CostPreviewPublic,
    RecipePublic,
    RecipesPublic,
    RecipeVersionCreate,
)

router = APIRouter(prefix="/recipes", tags=["recipes"])

Reader = Annotated[User, Depends(require_permission(Permission.RECIPES_READ))]
Manager = Annotated[User, Depends(require_permission(Permission.RECIPES_MANAGE))]


@router.get("/", response_model=RecipesPublic)
def read_recipes(
    session: SessionDep,
    _current_user: Reader,
    menu_item_id: uuid.UUID,
) -> Any:
    """
    Recipe and stock-link versions for one menu item, newest version first.
    """
    data, count = service.list_versions(session, menu_item_id=menu_item_id)
    return RecipesPublic(data=data, count=count)


@router.post("/", response_model=RecipePublic, status_code=201)
def create_recipe_version(
    session: SessionDep, actor: Manager, recipe_in: RecipeVersionCreate
) -> Any:
    """
    Save a new version. Prepared items take ingredient lines; direct-sale items
    take exactly one stock-link line. Earlier versions are left unchanged.
    """
    return service.create_version(session, data=recipe_in, actor=actor)


@router.get("/{recipe_id}", response_model=RecipePublic)
def read_recipe(
    session: SessionDep, _current_user: Reader, recipe_id: uuid.UUID
) -> Any:
    return service.get_version(session, recipe_id)


@router.get("/{recipe_id}/cost-preview", response_model=CostPreviewPublic)
def read_cost_preview(
    session: SessionDep, _current_user: Reader, recipe_id: uuid.UUID
) -> Any:
    """
    Estimated cost per serving from current average costs. Lines with no known
    cost are flagged and left out of the total.
    """
    return service.cost_preview(session, recipe_id)
