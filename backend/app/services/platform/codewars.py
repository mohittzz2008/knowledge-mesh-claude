"""Codewars Platform Connector.

Uses the public, unauthenticated Codewars API v1 (https://dev.codewars.com):

  GET /api/v1/users/{user}
  GET /api/v1/users/{user}/code-challenges/completed?page={n}   (200 per page)
  GET /api/v1/code-challenges/{slug}                            (kata detail)

Codewars has no "failed submission" feed, so evidence is built from completed
kata (each one a passed problem), the overall profile (honor / kyu rank), and a
bounded amount of per-kata detail (rank + tags) for the most recent completions.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from app.services.platform.base import BasePlatformConnector
from app.services.platform.errors import ConnectorError, UpstreamFormatError
from app.services.platform.http_util import clean_handle, get, make_client, path_segment

API_BASE = "https://www.codewars.com/api/v1"
SITE_BASE = "https://www.codewars.com"

MAX_COMPLETED_PAGES = 10  # 200 kata per page -> at most 2000 completions scanned
MAX_KATA_EVIDENCE = 25  # most recent completions persisted as evidence rows
MAX_KATA_DETAIL_LOOKUPS = 20  # of those, how many get a rank/tags lookup
DETAIL_CONCURRENCY = 4

LANGUAGE_DISPLAY = {
    "python": "Python",
    "c": "C",
    "cpp": "C++",
    "java": "Java",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "ruby": "Ruby",
    "csharp": "C#",
    "go": "Go",
    "rust": "Rust",
    "kotlin": "Kotlin",
    "swift": "Swift",
    "php": "PHP",
    "sql": "SQL",
    "shell": "Shell",
    "coffeescript": "CoffeeScript",
}


def display_language(code: str) -> str:
    return LANGUAGE_DISPLAY.get(code.lower(), code.capitalize())


class CodewarsConnector(BasePlatformConnector):
    """Integrates Codewars identity, honor/kyu rank, and completed kata."""

    platform_name = "Codewars"

    def __init__(
        self,
        auth_token: Optional[str] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        self.auth_token = auth_token  # Codewars API v1 is public; kept for interface parity
        self._transport = transport
        self._user_cache: dict[str, Optional[dict[str, Any]]] = {}

    # ------------------------------------------------------------------ fetch

    async def _get_user(self, handle: str) -> Optional[dict[str, Any]]:
        """Raw user object, or None when the user does not exist. Cached per instance."""
        key = handle.lower()
        if key in self._user_cache:
            return self._user_cache[key]

        async with make_client(self._transport) as client:
            response = await get(
                client,
                f"{API_BASE}/users/{path_segment(handle)}",
                platform=self.platform_name,
            )
        if response.status_code != 200:
            self._user_cache[key] = None
            return None

        try:
            data = response.json()
        except ValueError as err:
            raise UpstreamFormatError(
                "Codewars returned a response that was not valid JSON.",
                platform=self.platform_name,
            ) from err
        if not isinstance(data, dict) or not data.get("username"):
            self._user_cache[key] = None
            return None

        # The API also resolves user IDs; only accept the username that was asked for.
        if str(data["username"]).lower() != key:
            self._user_cache[key] = None
            return None

        self._user_cache[key] = data
        return data

    async def validate_identity(self, identifier: str, auth_type: str = "username_public") -> bool:
        handle = clean_handle(identifier)
        if not handle:
            return False
        return (await self._get_user(handle)) is not None

    async def fetch_profile(self, identifier: str) -> Optional[dict[str, Any]]:
        handle = clean_handle(identifier)
        if not handle:
            return None
        user = await self._get_user(handle)
        if not user:
            return None

        ranks = user.get("ranks") or {}
        overall = ranks.get("overall") or {}
        challenges = user.get("codeChallenges") or {}
        username = user["username"]

        language_ranks = {}
        for lang, info in (ranks.get("languages") or {}).items():
            if isinstance(info, dict):
                language_ranks[lang] = {
                    "rank": info.get("rank"),
                    "name": info.get("name"),
                    "score": info.get("score"),
                }

        return {
            "platform": self.platform_name,
            "username": username,
            "name": user.get("name") or username,
            "avatar_url": None,  # not exposed by API v1
            "html_url": f"{SITE_BASE}/users/{path_segment(username)}",
            "honor": user.get("honor", 0) or 0,
            "clan": user.get("clan") or None,
            "leaderboard_position": user.get("leaderboardPosition"),
            "rank": overall.get("rank"),
            "rank_name": overall.get("name"),
            "rank_score": overall.get("score"),
            "language_ranks": language_ranks,
            "total_solved": int(challenges.get("totalCompleted", 0) or 0),
            "total_authored": int(challenges.get("totalAuthored", 0) or 0),
        }

    async def _fetch_completed(self, handle: str) -> list[dict[str, Any]]:
        """All completed kata (bounded), most recent first."""
        completed: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        async with make_client(self._transport) as client:
            page = 0
            total_pages = 1
            while page < total_pages and page < MAX_COMPLETED_PAGES:
                response = await get(
                    client,
                    f"{API_BASE}/users/{path_segment(handle)}/code-challenges/completed",
                    platform=self.platform_name,
                    params={"page": page},
                )
                if response.status_code != 200:
                    if page > 0:
                        raise UpstreamUnavailableError(
                            f"Codewars completed challenges page {page} returned HTTP {response.status_code}.",
                            platform=self.platform_name,
                        )
                    break
                try:
                    body = response.json()
                except ValueError as err:
                    raise UpstreamFormatError(
                        "Codewars returned an unreadable completed-kata page.",
                        platform=self.platform_name,
                    ) from err
                if not isinstance(body, dict):
                    raise UpstreamFormatError(
                        "Codewars completed challenges response was not a JSON object.",
                        platform=self.platform_name,
                    )
                raw_data = body.get("data")
                if not isinstance(raw_data, list):
                    raise UpstreamFormatError(
                        "Codewars completed challenges data field is not a list.",
                        platform=self.platform_name,
                    )
                if not raw_data:
                    break
                for item in raw_data:
                    if isinstance(item, dict):
                        k_id = str(item.get("id") or item.get("slug") or "")
                        if k_id and k_id not in seen_ids:
                            seen_ids.add(k_id)
                            completed.append(item)
                total_pages = max(1, int(body.get("totalPages", 1) or 1))
                page += 1

        completed.sort(key=lambda k: k.get("completedAt") or "", reverse=True)
        return completed

    async def _fetch_kata_details(self, slugs: list[str]) -> dict[str, dict[str, Any]]:
        """Best-effort rank/tags for some kata. Never raises: enrichment is optional."""
        details: dict[str, dict[str, Any]] = {}
        unique_slugs = [s for s in dict.fromkeys(slugs) if s]
        if not unique_slugs:
            return details
        semaphore = asyncio.Semaphore(DETAIL_CONCURRENCY)

        async with make_client(self._transport) as client:

            async def one(slug: str) -> None:
                async with semaphore:
                    try:
                        response = await get(
                            client,
                            f"{API_BASE}/code-challenges/{path_segment(slug)}",
                            platform=self.platform_name,
                        )
                        if response.status_code == 200:
                            body = response.json()
                            if isinstance(body, dict) and (body.get("id") or body.get("slug") or body.get("name")):
                                details[slug] = body
                    except (ConnectorError, ValueError):
                        return  # rate-limited / flaky / odd JSON: skip this kata's extras

            await asyncio.gather(*(one(s) for s in unique_slugs))
        return details

    async def fetch_evidence(self, identifier: str) -> list[dict[str, Any]]:
        handle = clean_handle(identifier)
        if not handle:
            return []
        profile = await self.fetch_profile(handle)
        if not profile:
            return []

        username = profile["username"]
        completed = await self._fetch_completed(username)

        language_counts: dict[str, int] = {}
        for kata in completed:
            for code in set(kata.get("completedLanguages") or []):
                language_counts[code] = language_counts.get(code, 0) + 1

        recent = completed[:MAX_KATA_EVIDENCE]
        details = await self._fetch_kata_details(
            [k["slug"] for k in recent[:MAX_KATA_DETAIL_LOOKUPS] if k.get("slug")]
        )

        raw_items: list[dict[str, Any]] = [
            {
                "type": "codewars_profile_stats",
                "data": profile,
                "language_counts": language_counts,
            }
        ]
        for kata in recent:
            raw_items.append(
                {
                    "type": "codewars_kata",
                    "data": {**kata, "username": username},
                    "detail": details.get(kata.get("slug") or ""),
                }
            )
        return raw_items

    # -------------------------------------------------------------- normalize

    def normalize_evidence(self, raw_item: dict[str, Any]) -> dict[str, Any]:
        item_type = raw_item.get("type")
        data = raw_item.get("data", {}) or {}

        if item_type == "codewars_profile_stats":
            username = data.get("username", "")
            total = data.get("total_solved")
            total_display = total if total is not None else 0
            rank_name = data.get("rank_name") or "unranked"
            language_counts = raw_item.get("language_counts", {}) or {}
            top_languages = [
                display_language(code)
                for code, _ in sorted(language_counts.items(), key=lambda kv: kv[1], reverse=True)
            ]
            skills = (top_languages + ["Algorithms", "Problem Solving"]) if (total and total > 0) else []
            return {
                "platform": self.platform_name,
                "external_id": f"codewars_profile_{username.lower()}",
                "title": f"Codewars Profile: {username} ({total_display} Kata, {rank_name})",
                "evidence_type": "problem_solving_summary",
                "source_url": data.get("html_url"),
                "occurred_at": datetime.now(timezone.utc).isoformat(),
                "raw_payload": data,
                "normalized_payload": {
                    "total_solved": total,
                    "total_authored": data.get("total_authored", 0),
                    "honor": data.get("honor", 0),
                    "rank": data.get("rank"),
                    "rank_name": data.get("rank_name"),
                    "rank_score": data.get("rank_score"),
                    "leaderboard_position": data.get("leaderboard_position"),
                    "languages": top_languages,
                    "language_ranks": data.get("language_ranks", {}),
                    "skills": skills,
                },
            }

        if item_type == "codewars_kata":
            detail = raw_item.get("detail") or {}
            kata_id = data.get("id") or data.get("slug") or "unknown"
            slug = data.get("slug") or kata_id
            name = data.get("name") or "Codewars Kata"
            languages = [display_language(c) for c in dict.fromkeys(data.get("completedLanguages") or [])]
            tags = [t for t in (detail.get("tags") or []) if isinstance(t, str)]
            rank = detail.get("rank") or {}
            rank_name = rank.get("name") if isinstance(rank, dict) else None

            skills: list[str] = []
            for label in languages + tags + ["Algorithms", "Problem Solving"]:
                if label not in skills:
                    skills.append(label)

            title = f"Codewars Kata: {name}"
            if rank_name:
                title += f" ({rank_name})"

            return {
                "platform": self.platform_name,
                "external_id": f"codewars_kata_{kata_id}",
                "title": title[:255],
                "evidence_type": "problem_submission",
                "source_url": f"{SITE_BASE}/kata/{path_segment(str(slug))}",
                "occurred_at": data.get("completedAt"),  # None if missing, never fabricate timestamps!
                "raw_payload": {"completed": data, "detail": detail or None},
                "normalized_payload": {
                    "problem_title": name,
                    "title_slug": slug,
                    "status": "Completed",
                    "passed": True,
                    "languages": languages,
                    "difficulty": rank_name,
                    "tags": tags,
                    "skills": skills,
                },
            }

        return {}
