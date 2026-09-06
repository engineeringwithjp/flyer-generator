"""Consistency checks that Pydantic cannot express on its own."""

from __future__ import annotations

from ..models import Client, QAIssue, QAResult, Severity
from .loader import resolve_client_path


def validate_client(client: Client) -> QAResult:
    """Structural + business validation of a client profile."""
    issues: list[QAIssue] = []

    def error(check: str, message: str, detail: str = "") -> None:
        issues.append(QAIssue(check=check, severity=Severity.ERROR, message=message, detail=detail))

    def warn(check: str, message: str, detail: str = "") -> None:
        issues.append(
            QAIssue(check=check, severity=Severity.WARNING, message=message, detail=detail)
        )

    if not client.company_name.strip():
        error("company_name", "company_name is empty")

    if not client.services:
        error("services", "client offers no services - the campaign planner has nothing to pick")

    if not client.contact.has_any:
        error("contact", "no phone, website or email - flyers would have no call path")
    elif not client.contact.phone:
        warn("contact.phone", "no phone number; phone-call campaigns will be skipped")

    if client.brand.logo_path:
        if resolve_client_path(client, client.brand.logo_path) is None:
            warn(
                "brand.logo_path",
                f"logo not found at {client.brand.logo_path!r}; flyers will render without it",
            )
    else:
        warn("brand.logo_path", "no logo configured; flyers will use a wordmark fallback")

    if len(client.brand.primary_colors) == 0:
        error("brand.primary_colors", "at least one primary colour is required")

    offer_ids = [o.id for o in client.offers]
    if len(offer_ids) != len(set(offer_ids)):
        error("offers", "duplicate offer ids")

    for offer in client.offers:
        unknown = set(offer.services) - set(client.service_slugs) - {"general"}
        if unknown:
            warn(
                "offers.services",
                f"offer {offer.id!r} references services the client does not list",
                ", ".join(sorted(unknown)),
            )

    if not client.drive.root_folder_id:
        warn(
            "drive.root_folder_id",
            "no per-client Drive folder; the global GOOGLE_DRIVE_ROOT_FOLDER_ID will be used",
        )

    if not client.proof_points:
        warn(
            "proof_points",
            "no verified proof points - trust/credibility campaigns will have nothing to cite",
        )

    return QAResult.from_issues(issues, checked_by="client-validator")
