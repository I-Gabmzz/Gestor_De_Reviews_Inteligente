import pytest
from pydantic import ValidationError

from app.schemas.review import ReviewStatus, ReviewStatusUpdate


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("nueva", ReviewStatus.NUEVA),
        ("en_revision", ReviewStatus.EN_REVISION),
        ("atendida", ReviewStatus.ATENDIDA),
    ],
)
def test_review_status_update_accepts_official_statuses(
    status: str,
    expected: ReviewStatus,
) -> None:
    schema = ReviewStatusUpdate(estado=status)

    assert schema.estado is expected


@pytest.mark.parametrize("status", ["pendiente", "en revision", "ATENDIDA"])
def test_review_status_update_rejects_unknown_statuses(status: str) -> None:
    with pytest.raises(ValidationError):
        ReviewStatusUpdate(estado=status)
