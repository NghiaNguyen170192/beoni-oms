from typing import Annotated

from fastapi import Depends, Header, HTTPException

IDEMPOTENCY_KEY_HEADER = "Idempotency-Key"


def get_idempotency_key(
    idempotency_key: Annotated[
        str | None, Header(alias=IDEMPOTENCY_KEY_HEADER, max_length=255)
    ] = None,
) -> str:
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(
            status_code=400, detail=f"{IDEMPOTENCY_KEY_HEADER} header is required"
        )
    return idempotency_key.strip()


IdempotencyKeyDep = Annotated[str, Depends(get_idempotency_key)]
