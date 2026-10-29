"""Backward-compatible pagination for record-list endpoints."""
from typing import Callable, Literal, TypeVar

from fastapi import HTTPException


PageSize = int | Literal["all"]
ALLOWED_PAGE_SIZES = (10, 25, 50)
T = TypeVar("T")
R = TypeVar("R")


def paginate_records(records: list[T], page: int | None, page_size: PageSize,
                     serialize: Callable[[T], R]) -> list[R] | dict[str, object]:
    """Return the legacy array without `page`, otherwise a paginated envelope."""
    if page_size != "all" and page_size not in ALLOWED_PAGE_SIZES:
        raise HTTPException(422, "Page size must be 10, 25, 50 or all")
    if page is None:
        return [serialize(record) for record in records]
    if page < 1:
        raise HTTPException(422, "Page must be positive")

    total = len(records)
    if page_size == "all":
        selected = records
        returned_page = 1
    else:
        start = (page - 1) * page_size
        selected = records[start:start + page_size]
        returned_page = page
    return {
        "items": [serialize(record) for record in selected],
        "total": total,
        "page": returned_page,
        "page_size": page_size,
    }
