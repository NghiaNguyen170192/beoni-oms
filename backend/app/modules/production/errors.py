from app.core.errors import Conflict, Forbidden, Invalid, NotFound


class BatchNotFound(NotFound):
    default_detail = "Production batch not found"


class BatchNotDraft(Conflict):
    default_detail = "Only draft production batches can be edited"


class BatchNotCompletable(Conflict):
    default_detail = "Only draft production batches can be completed"


class BatchNotReversible(Conflict):
    default_detail = "Only completed production batches can be reversed"


class BatchBackdatePermissionRequired(Forbidden):
    default_detail = "Backdating batch completion requires additional permission"


class BatchHasDownstreamActivity(Conflict):
    default_detail = (
        "A production batch cannot be reversed after its finished goods have moved"
    )


class InvalidBatchCompletion(Invalid):
    default_detail = (
        "Completion must account for every planned line and include consumed material "
        "and good or waste output"
    )


class EmptyBatchUpdate(Invalid):
    default_detail = "At least one batch field must be updated"


class BatchMenuItemNotFound(NotFound):
    default_detail = "A production output menu item was not found"


class InvalidBatchInput(Conflict):
    default_detail = "Production inputs must be active raw-material inventory items"


class InvalidBatchOutput(Conflict):
    default_detail = (
        "Production outputs must use active finished-good inventory items "
        "and active sellable menu items"
    )


class BatchOutputMappingConflict(Conflict):
    default_detail = "A menu item must keep the same finished-good inventory mapping"


class InvalidProductionFormula(Conflict):
    default_detail = "The selected recipe version is not a usable production formula"
