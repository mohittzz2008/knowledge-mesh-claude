"""Exercism Platform Connector."""

from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from app.services.platform.base import BasePlatformConnector
from app.services.platform.errors import (
    ConnectorError,
    RateLimitedError,
    UpstreamFormatError,
    UpstreamUnavailableError,
)
from app.services.platform.http_util import clean_handle, get, make_client, path_segment

EXERCISM_API_URL = "https://exercism.org/api/v2"


class ExercismConnector(BasePlatformConnector):
    """Exercism Connector using public reputation data and optional authenticated API token."""

    platform_name = "Exercism"

    def __init__(
        self,
        auth_token: Optional[str] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        self.auth_token = auth_token.strip() if auth_token and auth_token.strip() else None
        self.transport = transport

    def _headers(self) -> dict[str, str]:
        headers = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    async def validate_identity(self, identifier: str, auth_type: str = "username_public") -> bool:
        """Validate Exercism username via public API."""
        handle = clean_handle(identifier)
        if not handle:
            return False

        url = f"{EXERCISM_API_URL}/users/{path_segment(handle)}"
        async with make_client(transport=self.transport, headers=self._headers()) as client:
            try:
                res = await get(client, url, platform=self.platform_name)
                if res.status_code == 200:
                    try:
                        data = res.json()
                    except Exception:
                        return False
                    if not isinstance(data, dict):
                        return False
                    returned_handle = data.get("handle", "")
                    return bool(returned_handle and returned_handle.lower() == handle.lower())
                if res.status_code == 404:
                    return False
            except (RateLimitedError, UpstreamUnavailableError):
                raise
            except Exception as err:
                raise UpstreamUnavailableError(
                    f"Could not reach {self.platform_name}: {err}",
                    platform=self.platform_name,
                ) from err
        return False

    async def fetch_solutions(self, handle: str) -> Optional[list[dict[str, Any]]]:
        """Fetch completed solutions if an auth token is provided."""
        if not self.auth_token:
            return None

        url = f"{EXERCISM_API_URL}/solutions"
        async with make_client(transport=self.transport, headers=self._headers()) as client:
            try:
                res = await client.get(url)
                if res.status_code == 401:
                    err = ConnectorError(
                        "Exercism authentication failed: invalid API key.",
                        platform=self.platform_name,
                    )
                    err.status_code = 401
                    raise err
                if res.status_code == 429:
                    raise RateLimitedError(
                        f"{self.platform_name} rate limit reached. Please try again in a minute.",
                        platform=self.platform_name,
                    )
                if res.status_code >= 500:
                    raise UpstreamUnavailableError(
                        f"{self.platform_name} is temporarily unavailable (HTTP {res.status_code}).",
                        platform=self.platform_name,
                    )
                if res.status_code == 200:
                    try:
                        data = res.json()
                    except Exception as err:
                        raise UpstreamFormatError(
                            "Malformed JSON from Exercism solutions API",
                            platform=self.platform_name,
                        ) from err
                    if isinstance(data, dict):
                        results = data.get("results", [])
                        return results if isinstance(results, list) else []
                    if isinstance(data, list):
                        return data
                return None
            except (ConnectorError, RateLimitedError, UpstreamUnavailableError, UpstreamFormatError):
                raise
            except (httpx.TimeoutException, httpx.RequestError) as err:
                raise UpstreamUnavailableError(
                    f"Could not reach {self.platform_name}: {err}",
                    platform=self.platform_name,
                ) from err
            except Exception:
                return None

    async def fetch_profile(self, identifier: str) -> Optional[dict[str, Any]]:
        """Fetch Exercism profile, reputation, and optional solutions."""
        handle = clean_handle(identifier)
        if not handle:
            return None

        url = f"{EXERCISM_API_URL}/users/{path_segment(handle)}"
        async with make_client(transport=self.transport, headers=self._headers()) as client:
            try:
                res = await get(client, url, platform=self.platform_name)
            except (RateLimitedError, UpstreamUnavailableError):
                raise
            except Exception as err:
                raise UpstreamUnavailableError(
                    f"Could not reach {self.platform_name}: {err}",
                    platform=self.platform_name,
                ) from err

            if res.status_code == 404:
                return None
            if res.status_code != 200:
                raise UpstreamUnavailableError(
                    f"{self.platform_name} returned HTTP {res.status_code}",
                    platform=self.platform_name,
                )

            try:
                data = res.json()
            except Exception as err:
                raise UpstreamFormatError(
                    f"Malformed response from {self.platform_name}",
                    platform=self.platform_name,
                ) from err

            if not isinstance(data, dict):
                return None

            returned_handle = data.get("handle", "")
            if returned_handle.lower() != handle.lower():
                return None

            reputation = data.get("reputation")
            total_rep = None
            skills = []
            if isinstance(reputation, dict):
                total_rep = reputation.get("total")
                tracks = reputation.get("tracks")
                if isinstance(tracks, dict):
                    skills = list(tracks.keys())
            elif reputation is not None:
                total_rep = reputation

            # Attempt to fetch completed exercises if token is provided
            total_solved = None
            if self.auth_token:
                solutions = await self.fetch_solutions(handle)
                if solutions is not None:
                    unique_exercises = set()
                    for sol in solutions:
                        if isinstance(sol, dict):
                            status = str(sol.get("status", "")).lower()
                            if status in ("completed", "published", "solved", "iterating", ""):
                                ex = sol.get("exercise")
                                tr = sol.get("track")
                                ex_slug = ex.get("slug") if isinstance(ex, dict) else ex
                                tr_slug = tr.get("slug") if isinstance(tr, dict) else tr
                                if ex_slug and tr_slug:
                                    unique_exercises.add(f"{tr_slug}:{ex_slug}")
                                elif ex_slug:
                                    unique_exercises.add(str(ex_slug))
                    total_solved = len(unique_exercises) if unique_exercises else len(solutions)

            return {
                "platform": self.platform_name,
                "username": returned_handle,
                "handle": returned_handle,
                "name": returned_handle,
                "avatar_url": data.get("avatar_url"),
                "html_url": f"https://exercism.org/profiles/{path_segment(returned_handle)}",
                "flair": data.get("flair"),
                "has_profile": data.get("has_profile", True),
                "reputation": total_rep,
                "total_reputation": total_rep,
                "tracks": skills,
                "skills": skills,
                "active_tracks_count": len(skills),
                "total_solved": total_solved,
            }

    async def fetch_evidence(self, identifier: str) -> list[dict[str, Any]]:
        """Fetch Exercism evidence (reputation metrics and authenticated solutions)."""
        handle = clean_handle(identifier)
        if not handle:
            return []

        profile = await self.fetch_profile(handle)
        if not profile:
            return []

        raw_items: list[dict[str, Any]] = [
            {
                "type": "exercism_reputation",
                "data": profile,
                "total_solved": profile.get("total_solved"),
            }
        ]

        if self.auth_token:
            solutions = await self.fetch_solutions(handle)
            for sol in solutions:
                if isinstance(sol, dict):
                    raw_items.append({
                        "type": "exercism_solution",
                        "data": sol,
                        "username": profile["username"],
                    })

        return raw_items

    def normalize_evidence(self, raw_item: dict[str, Any]) -> dict[str, Any]:
        """Normalize Exercism payload into Knowledge Mesh schema."""
        item_type = raw_item.get("type", "exercism_reputation")
        data = raw_item.get("data", {}) or {}

        if item_type == "exercism_reputation":
            handle = data.get("username") or data.get("handle") or ""
            reputation = data.get("reputation")
            if isinstance(reputation, dict):
                total_rep = reputation.get("total")
            else:
                total_rep = reputation if reputation is not None else data.get("total_reputation")

            tracks = data.get("tracks") or data.get("skills") or []
            if isinstance(tracks, dict):
                skills = list(tracks.keys())
            elif isinstance(tracks, list):
                skills = list(tracks)
            else:
                skills = []

            total_solved = raw_item.get("total_solved")
            if total_solved is None:
                total_solved = data.get("total_solved")

            title_suffix = f" (Reputation: {total_rep})" if total_rep is not None else ""

            return {
                "platform": self.platform_name,
                "external_id": f"exercism_profile_{handle.lower()}",
                "title": f"Exercism Profile: {handle}{title_suffix}",
                "evidence_type": "problem_solving_summary",
                "source_url": data.get("html_url") or f"https://exercism.org/profiles/{handle}",
                "occurred_at": datetime.now(timezone.utc).isoformat(),
                "raw_payload": data,
                "normalized_payload": {
                    "reputation": total_rep,
                    "total_reputation": total_rep,
                    "active_tracks_count": len(skills),
                    "skills": skills,
                    "total_solved": total_solved,
                },
            }

        if item_type == "exercism_solution":
            track_info = data.get("track")
            track = (
                track_info.get("slug")
                if isinstance(track_info, dict)
                else (track_info or "unknown")
            )
            exercise_info = data.get("exercise")
            exercise_slug = (
                exercise_info.get("slug")
                if isinstance(exercise_info, dict)
                else (data.get("exercise_slug") or "exercise")
            )
            exercise_title = (
                exercise_info.get("title")
                if isinstance(exercise_info, dict)
                else (data.get("exercise_title") or exercise_slug)
            )
            uuid = data.get("uuid") or f"{track}_{exercise_slug}"

            occurred_at = (
                data.get("completed_at")
                or data.get("published_at")
                or datetime.now(timezone.utc).isoformat()
            )

            return {
                "platform": self.platform_name,
                "external_id": f"exercism_solution_{uuid}",
                "title": f"Exercism Solution: {exercise_title} ({track})",
                "evidence_type": "problem_submission",
                "source_url": (
                    data.get("url")
                    or f"https://exercism.org/tracks/{track}/exercises/{exercise_slug}"
                ),
                "occurred_at": occurred_at,
                "raw_payload": data,
                "normalized_payload": {
                    "uuid": uuid,
                    "exercise": exercise_slug,
                    "exercise_title": exercise_title,
                    "track": track,
                    "status": data.get("status", "completed"),
                    "skills": [track] if track else [],
                },
            }

        return {}
