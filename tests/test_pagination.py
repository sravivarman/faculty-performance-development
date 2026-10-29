import pytest
from fastapi import HTTPException

from backend.pagination import paginate_records


def test_paginated_envelope_is_deterministic_and_all_preserves_every_filtered_record():
    records = list(range(51))
    legacy = paginate_records(records, None, 25, lambda value: {"id": value})
    first = paginate_records(records, 1, 10, lambda value: {"id": value})
    second = paginate_records(records, 2, 10, lambda value: {"id": value})
    large = paginate_records(records, 1, 50, lambda value: {"id": value})
    all_rows = paginate_records(records, 1, "all", lambda value: {"id": value})

    assert [row["id"] for row in legacy] == records
    assert first == {"items": [{"id": value} for value in range(10)], "total": 51, "page": 1, "page_size": 10}
    assert [row["id"] for row in second["items"]] == list(range(10, 20))
    assert len(large["items"]) == 50 and large["total"] == 51
    assert [row["id"] for row in all_rows["items"]] == records
    assert all_rows["page"] == 1 and all_rows["page_size"] == "all"


def test_pagination_rejects_invalid_page_and_page_size():
    with pytest.raises(HTTPException):
        paginate_records([], 0, 10, lambda value: value)
    with pytest.raises(HTTPException):
        paginate_records([], 1, 100, lambda value: value)
