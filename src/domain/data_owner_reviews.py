from __future__ import annotations

from datetime import date
from typing import Any

ALLOWED_STATUSES = {"open", "under_review", "approved", "rejected", "expired"}


def validate_reviews(reviews: list[dict[str, Any]], today: date) -> list[str]:
    errors: list[str] = []
    required_column = "billing.pagamenti.riferimento_bancario"
    indexed = {f"{item.get('schema')}.{item.get('table')}.{item.get('column')}": item for item in reviews}
    if required_column not in indexed:
        errors.append("required review missing")
    for review in reviews:
        status = review.get("status")
        if status not in ALLOWED_STATUSES:
            errors.append("invalid status")
        if status == "approved":
            if not review.get("approver"):
                errors.append("approver missing")
            if not review.get("residual_risk"):
                errors.append("residual risk missing")
            if review.get("decision") != review.get("masking_strategy"):
                errors.append("strategy not approved")
            next_review = review.get("next_review_date")
            if not isinstance(next_review, date) or next_review < today:
                errors.append("review expired")
    return sorted(set(errors))
