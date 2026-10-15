"""API endpoints for Multi-Platform Connectors, Central Registry, and Ingestion."""

import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_user
from app.database import get_db
from app.models.code_artifact import CodeArtifact
from app.models.evidence import Evidence
from app.models.platform import PlatformConnection
from app.models.user import User
from app.schemas.platform import (
    PlatformRegistryItemSchema,
    PlatformSyncRequest,
    PlatformSyncResponse,
    PlatformValidateRequest,
    PlatformValidateResponse,
)
from app.services.mesh.concept_extractor import ConceptExtractorService
from app.services.platform.base import BasePlatformConnector
from app.services.platform.errors import ConnectorError
from app.services.platform.registry import PlatformRegistry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/platforms", tags=["Platforms"])

# profile key -> label, shown as quick facts after a sync
HIGHLIGHT_LABELS = {
    "rank_name": "Rank",
    "honor": "Honor",
    "coding_score": "Coding score",
    "institute_rank": "Institute rank",
    "streak": "Streak",
    "stars": "Stars",
    "global_rank": "Global rank",
    "ranking": "Global ranking",
    "rating": "Rating",
    "current_rating": "Rating",
    "reputation": "Reputation",
}


def _get_connector(platform_key: str, auth_token: str | None = None) -> BasePlatformConnector:
    connector = PlatformRegistry.get_connector_instance(platform_key, auth_token=auth_token)
    if not connector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Platform connector '{platform_key}' is not registered.",
        )
    return connector


def _http_error(err: Exception, platform: str) -> HTTPException:
    """Translate a connector / network failure into a precise HTTP error."""
    if isinstance(err, ConnectorError):
        return HTTPException(status_code=err.status_code, detail=str(err))
    if isinstance(err, httpx.TimeoutException):
        return HTTPException(status_code=504, detail=f"{platform} timed out. Please try again.")
    if isinstance(err, httpx.HTTPError):
        return HTTPException(status_code=502, detail=f"Could not reach {platform}. Please try again.")
    if isinstance(err, RuntimeError) and "rate limit" in str(err).lower():
        return HTTPException(status_code=429, detail=str(err))
    logger.exception("Unexpected %s connector failure", platform, exc_info=err)
    return HTTPException(status_code=500, detail=f"{platform} sync failed unexpectedly.")


def _highlights(profile: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for key, label in HIGHLIGHT_LABELS.items():
        value = profile.get(key)
        if isinstance(value, dict) and "total" in value:
            value = value.get("total")
        if value not in (None, "") and not any(h["label"] == label for h in out):
            if value == 0 and key not in ("reputation",):
                continue
            out.append({"label": label, "value": value})
    return out


@router.get("", response_model=list[PlatformRegistryItemSchema])
def list_registered_platforms(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List registered developer platform connectors, capabilities, and connection states."""
    user_connections = db.query(PlatformConnection).filter(PlatformConnection.user_id == current_user.id).all()
    conn_map = {c.platform.lower(): c for c in user_connections}

    result = []
    for item in PlatformRegistry.list_items():
        d = item.to_dict()
        conn = conn_map.get(item.connector_class.platform_name.lower())
        d["connected"] = bool(conn and conn.connected)
        d["connected_username"] = conn.username if conn and conn.connected else None
        d["last_synced_at"] = conn.last_synced_at if conn else None
        result.append(PlatformRegistryItemSchema.model_validate(d))
    return result


@router.post("/{platform_key}/validate", response_model=PlatformValidateResponse)
async def validate_platform_identity(
    platform_key: str,
    payload: PlatformValidateRequest,
    current_user: User = Depends(get_current_user),  # authenticated: this endpoint calls third parties
):
    """Validate that a username exists on the platform."""
    connector = _get_connector(platform_key)
    username = payload.username.strip()

    try:
        is_valid = await connector.validate_identity(username)
        if not is_valid:
            return PlatformValidateResponse(
                platform=connector.platform_name,
                username=username,
                valid=False,
                detail=f"{connector.platform_name} identity '{username}' was not found or is inaccessible.",
            )
        profile_data = await connector.fetch_profile(username) or {}
    except Exception as err:  # noqa: BLE001 - mapped to a precise HTTP error
        raise _http_error(err, connector.platform_name) from err

    return PlatformValidateResponse(
        platform=connector.platform_name,
        username=username,
        valid=True,
        avatar_url=profile_data.get("avatar_url"),
        bio=profile_data.get("bio"),
        public_repos=profile_data.get("public_repos", 0),
        followers=profile_data.get("followers", 0),
        total_solved=profile_data.get("total_solved"),
        detail=f"{connector.platform_name} identity verified successfully.",
    )


@router.post("/{platform_key}/disconnect")
def disconnect_platform(
    platform_key: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Disconnect a platform and recalculate assessments without deleting historical evidence."""
    connector = _get_connector(platform_key)

    connection = (
        db.query(PlatformConnection)
        .filter(
            PlatformConnection.user_id == current_user.id,
            PlatformConnection.platform == connector.platform_name,
        )
        .first()
    )
    if connection and connection.connected:
        connection.connected = False
        db.commit()

        # Recalculate mesh to drop disconnected evidence
        ConceptExtractorService().extract_and_assess_user_skills(current_user.id, db)

    return {"message": f"Successfully disconnected {connector.platform_name}."}


def _parse_occurred_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


@router.post("/{platform_key}/sync", response_model=PlatformSyncResponse)
async def sync_platform_data(
    platform_key: str,
    payload: PlatformSyncRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Ingest, normalize, and persist developer evidence for one platform."""
    connector = _get_connector(platform_key, auth_token=payload.auth_token)
    username = payload.username.strip()
    user = current_user

    logger.info("platform sync start user=%s platform=%s username=%s", user.id, connector.platform_name, username)

    # 1. Talk to the platform FIRST. Nothing is written until we know the sync can succeed,
    #    so a flaky upstream can never leave a "connected" platform with no data.
    try:
        if not await connector.validate_identity(username):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{connector.platform_name} user '{username}' not found on platform.",
            )
        profile_data = await connector.fetch_profile(username) or {}
        raw_evidence_list = await connector.fetch_evidence(username)
    except HTTPException:
        raise
    except Exception as err:  # noqa: BLE001 - mapped to a precise HTTP error
        raise _http_error(err, connector.platform_name) from err

    # 2. Find or create the PlatformConnection.
    connection = (
        db.query(PlatformConnection)
        .filter(
            PlatformConnection.user_id == user.id,
            PlatformConnection.platform == connector.platform_name,
        )
        .first()
    )
    if not connection:
        connection = PlatformConnection(
            user_id=user.id,
            platform=connector.platform_name,
            auth_type=payload.auth_type,
            username=username,
            connected=True,
        )
        db.add(connection)
        db.flush()
    else:
        # Switching to a genuinely different account: purge the previous account's evidence.
        # (Case-only changes are the same account.)
        if (connection.username or "").lower() != username.lower():
            logger.info(
                "username switch on %s: %r -> %r; purging stale evidence",
                connector.platform_name, connection.username, username,
            )
            db.query(Evidence).filter(Evidence.platform_connection_id == connection.id).delete()
            db.query(CodeArtifact).filter(
                CodeArtifact.platform_connection_id == connection.id,
                CodeArtifact.platform != "CodeLab",
            ).delete()
        connection.username = username
        connection.auth_type = payload.auth_type
        connection.connected = True

    # 3. Upsert evidence. Existing rows are refreshed (so profile stats don't go stale);
    #    autoflush is off, so in-batch duplicates are tracked explicitly.
    existing_by_external_id = {
        e.external_id: e
        for e in db.query(Evidence).filter(Evidence.platform_connection_id == connection.id).all()
        if e.external_id
    }
    inserted = 0
    updated = 0
    for item in raw_evidence_list:
        normalized = connector.normalize_evidence(item)
        if not normalized:
            continue  # connector declined to normalise this item

        external_id = normalized.get("external_id")
        title = (normalized.get("title") or f"{connector.platform_name} Evidence")[:255]
        occurred_at = _parse_occurred_at(normalized.get("occurred_at"))

        existing = existing_by_external_id.get(external_id) if external_id else None
        if not existing and external_id:
            # Check for legacy un-prefixed external_id (e.g., "12345" matching "github_repo_12345")
            raw_suffix = external_id.split("_", 2)[-1] if "_" in external_id else None
            if raw_suffix and raw_suffix in existing_by_external_id:
                existing = existing_by_external_id[raw_suffix]
                existing.external_id = external_id

        if existing:
            existing.title = title
            existing.evidence_type = normalized.get("evidence_type", existing.evidence_type)
            existing.raw_payload = normalized.get("raw_payload")
            existing.normalized_payload = normalized.get("normalized_payload")
            if occurred_at:
                existing.occurred_at = occurred_at
            updated += 1
            continue

        record = Evidence(
            user_id=user.id,
            platform_connection_id=connection.id,
            external_id=external_id,
            title=title,
            evidence_type=normalized.get("evidence_type", "activity"),
            raw_payload=normalized.get("raw_payload"),
            normalized_payload=normalized.get("normalized_payload"),
            occurred_at=occurred_at,
        )
        db.add(record)
        if external_id:
            existing_by_external_id[external_id] = record
        inserted += 1

    connection.last_synced_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(connection)

    logger.info(
        "platform sync stored platform=%s inserted=%d updated=%d", connector.platform_name, inserted, updated
    )

    # 4. Re-evaluate Knowledge Mesh skill assessments.
    ConceptExtractorService().extract_and_assess_user_skills(user.id, db)

    if inserted > 0:
        message = f"Ingested {inserted} new {connector.platform_name} evidence item(s) for '{username}'."
    elif updated > 0:
        message = f"Refreshed {updated} existing {connector.platform_name} evidence item(s) for '{username}'. Nothing new since the last sync."
    else:
        message = f"Sync complete for '{username}'. No public evidence items found on {connector.platform_name}."

    return PlatformSyncResponse(
        platform_connection_id=connection.id,
        platform=connector.platform_name,
        username=username,
        connected=True,
        synced_evidence_count=inserted,
        updated_evidence_count=updated,
        profile_summary={
            "public_repos": profile_data.get("public_repos", 0),
            "total_solved": profile_data.get("total_solved"),
            "followers": profile_data.get("followers", 0),
            "avatar_url": profile_data.get("avatar_url"),
            "html_url": profile_data.get("html_url"),
            "bio": profile_data.get("bio"),
            "highlights": _highlights(profile_data),
        },
        last_synced_at=connection.last_synced_at,
        message=message,
    )
