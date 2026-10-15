"""HackerRank Platform Connector using REST API Ingestion."""

import asyncio
from datetime import datetime
from typing import Any, Optional
import httpx

from app.services.platform.base import BasePlatformConnector
from app.services.platform.errors import RateLimitedError, UpstreamUnavailableError
from app.services.platform.http_util import clean_handle, get, make_client, path_segment

HACKERRANK_API_BASE = "https://www.hackerrank.com/rest/hackers"
DEFAULT_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


class HackerRankConnector(BasePlatformConnector):
    """HackerRank Connector fetching badges & profile telemetry via REST API."""

    platform_name = "HackerRank"

    def __init__(
        self,
        auth_token: Optional[str] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        self.auth_token = auth_token
        self.transport = transport
        self.headers = dict(DEFAULT_HEADERS)

    async def validate_identity(self, identifier: str, auth_type: str = "username_public") -> bool:
        """Validate if a public HackerRank username exists via official REST API."""
        handle = clean_handle(identifier)
        if not handle:
            return False

        url = f"https://www.hackerrank.com/rest/contests/master/hackers/{path_segment(handle)}/profile"
        async with make_client(transport=self.transport, headers=self.headers) as client:
            res = await get(client, url, platform=self.platform_name)
            if res.status_code == 200:
                data = res.json()
                model = data.get("model") or {}
                returned_user = model.get("username")
                if returned_user and returned_user.lower() == handle.lower():
                    return True
            elif res.status_code == 404:
                return False
        return False

    async def fetch_profile(
        self, identifier: str, badges: Optional[list[dict[str, Any]]] = None
    ) -> Optional[dict[str, Any]]:
        """Fetch HackerRank profile statistics and badges.
        
        Note on solved count semantics:
        HackerRank does not provide a verified lifetime unique solved problem counter
        in its public REST API. Domain badges (e.g. Problem Solving, Python, C) represent
        domain-specific challenges that overlap and cannot be summed into unique solves.
        Lifetime unique total_solved is therefore represented as None (unknown) to avoid
        fabricating or double-counting solved challenges. Badge-level counts are preserved
        separately on individual badge evidence records.
        """
        handle = clean_handle(identifier)
        if not handle:
            return None

        url = f"https://www.hackerrank.com/rest/contests/master/hackers/{path_segment(handle)}/profile"
        async with make_client(transport=self.transport, headers=self.headers) as client:
            res = await get(client, url, platform=self.platform_name)
            if res.status_code == 200:
                m = res.json().get("model", {})
                username = m.get("username") or handle

                return {
                    "platform": self.platform_name,
                    "username": username,
                    "name": m.get("name") or username,
                    "avatar_url": m.get("avatar"),
                    "html_url": f"https://www.hackerrank.com/profile/{username}",
                    "country": m.get("country"),
                    "school": m.get("school"),
                    "level": m.get("level", 1),
                    "total_solved": None,  # Not provided upstream; do not sum overlapping badges
                }
            elif res.status_code == 404:
                return None
        return None

    async def fetch_badges(self, username: str) -> list[dict[str, Any]]:
        """Fetch developer HackerRank skill badges (Algorithms, Python, Problem Solving)."""
        handle = clean_handle(username)
        if not handle:
            return []

        url = f"{HACKERRANK_API_BASE}/{path_segment(handle)}/badges"
        async with make_client(transport=self.transport, headers=self.headers) as client:
            res = await get(client, url, platform=self.platform_name)
            if res.status_code == 200:
                return res.json().get("models", [])
            elif res.status_code == 404:
                return []
        return []

    async def fetch_challenge_metadata(
        self, challenge_slug: str, client: Optional[httpx.AsyncClient] = None
    ) -> Optional[dict[str, Any]]:
        """Fetch metadata for a challenge (track, subdomain, topic) via REST API."""
        if not challenge_slug or not challenge_slug.strip():
            return None
        url = f"https://www.hackerrank.com/rest/contests/master/challenges/{path_segment(challenge_slug.strip())}"
        try:
            if client:
                res = await get(client, url, platform=self.platform_name)
            else:
                async with make_client(transport=self.transport, headers=self.headers) as c:
                    res = await get(c, url, platform=self.platform_name)
            if res.status_code == 200:
                return res.json().get("model", {})
        except (UpstreamUnavailableError, RateLimitedError):
            pass
        return None

    async def fetch_recent_challenges(
        self, identifier: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Fetch recently solved HackerRank challenges with verified topic/track metadata."""
        handle = clean_handle(identifier)
        if not handle:
            return []

        url = f"{HACKERRANK_API_BASE}/{path_segment(handle)}/recent_challenges?offset=0&limit={limit}"
        async with make_client(transport=self.transport, headers=self.headers) as client:
            res = await get(client, url, platform=self.platform_name)
            if res.status_code == 200:
                raw_challenges = res.json().get("models", [])
            elif res.status_code == 404:
                return []
            else:
                return []

            # Enrich with track/topic metadata only when required
            enriched_challenges: list[dict[str, Any]] = []
            tasks = []
            indices_to_fetch = []

            for idx, ch in enumerate(raw_challenges):
                # If topic/track info is already present, use directly
                if ch.get("track") or ch.get("topic") or ch.get("topics"):
                    enriched_challenges.append(ch)
                else:
                    slug = ch.get("ch_slug") or ch.get("slug")
                    if slug:
                        tasks.append(self.fetch_challenge_metadata(slug, client=client))
                        indices_to_fetch.append(idx)
                    enriched_challenges.append(dict(ch))

            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for idx, meta in zip(indices_to_fetch, results):
                    if isinstance(meta, dict) and meta:
                        enriched_challenges[idx]["track"] = meta.get("track")
                        enriched_challenges[idx]["preview"] = meta.get("preview")
                        enriched_challenges[idx]["difficulty_name"] = meta.get("difficulty_name")

            return enriched_challenges

    async def fetch_evidence(self, identifier: str) -> list[dict[str, Any]]:
        """Fetch HackerRank skill badges and recent solved challenge telemetry evidence."""
        handle = clean_handle(identifier)
        if not handle:
            return []

        badges = await self.fetch_badges(handle)
        profile = await self.fetch_profile(handle, badges=badges)
        challenges = await self.fetch_recent_challenges(handle)

        raw_items = []
        if profile:
            raw_items.append({
                "type": "hackerrank_profile",
                "data": profile,
            })

        for b in badges:
            raw_items.append({
                "type": "hackerrank_badge",
                "data": b,
            })

        for ch in challenges:
            raw_items.append({
                "type": "hackerrank_challenge",
                "data": ch,
            })

        return raw_items

    def _extract_challenge_skills(self, data: dict[str, Any]) -> list[str]:
        """Extract verified topic skills from HackerRank challenge metadata."""
        # 1. Direct skills if already provided in raw payload
        raw_skills = data.get("skills")
        if isinstance(raw_skills, list) and raw_skills:
            return [s for s in raw_skills if isinstance(s, str)]

        skills: list[str] = []

        # 2. Extract track and challenge attributes
        track = data.get("track") or {}
        track_name = str(track.get("track_name") or data.get("track_name") or "").strip()
        sub_name = str(track.get("name") or data.get("sub_name") or "").strip()
        sub_slug = str(track.get("slug") or data.get("sub_slug") or "").strip().lower()
        ch_name = str(data.get("name") or data.get("title") or "").strip()
        ch_slug = str(data.get("ch_slug") or data.get("slug") or "").strip().lower()
        preview = str(data.get("preview") or "").lower()
        ch_name_lower = ch_name.lower()

        # Topic detection based strictly on verified HackerRank metadata
        # Sets: track is Sets or sub_slug is py-sets or explicit set challenge
        if (
            sub_name.lower() == "sets"
            or sub_slug == "py-sets"
            or ch_slug.startswith("py-set")
            or "set" in sub_slug
            or "sets" in ch_slug
            or "sets" in ch_name_lower
            or ch_name_lower.startswith("set ")
        ):
            skills.append("Sets")

        # Functions: explicit function challenge in Introduction or title/slug
        elif (
            sub_name.lower() == "functions"
            or "function" in ch_slug
            or "function" in ch_name_lower
        ):
            skills.append("Functions")

        # Lists / List Comprehensions: Basic Data Types list challenges or title/slug
        elif (
            sub_name.lower() == "lists"
            or sub_slug == "py-lists"
            or "list" in ch_slug
            or "list" in ch_name_lower
        ):
            if "list comprehension" in ch_name_lower or "list-comprehension" in ch_slug:
                skills.append("List Comprehensions")
            skills.append("Lists")

        # Arrays: Warmup array challenge (Simple Array Sum) or Arrays subdomain
        elif (
            sub_name.lower() == "arrays"
            or sub_slug == "arrays"
            or "array" in ch_slug
            or "array" in ch_name_lower
        ):
            skills.append("Arrays")

        # Dictionaries:
        elif (
            sub_name.lower() in ("dictionaries", "hash map", "dict")
            or "dict" in ch_slug
            or "dictionary" in ch_name_lower
        ):
            skills.append("Dictionaries")

        # Trees:
        elif sub_name.lower() in ("trees", "binary search tree") or "tree" in ch_slug:
            skills.append("Tree Traversal")

        # DFS:
        elif "dfs" in ch_slug or "depth-first" in ch_name_lower:
            skills.append("DFS")

        # Add domain-level track skills
        if track_name.lower() == "algorithms" or sub_name.lower() == "warmup":
            if "Algorithms" not in skills:
                skills.append("Algorithms")
            if "Problem Solving" not in skills:
                skills.append("Problem Solving")
        elif track_name.lower() == "python":
            if "Python" not in skills:
                skills.append("Python")
        elif track_name.lower() == "c":
            if "C" not in skills:
                skills.append("C")

        # Fallback if no skills identified yet
        if not skills:
            if sub_name:
                skills.append(sub_name)
            elif track_name:
                skills.append(track_name)
            else:
                skills.append("Problem Solving")

        return skills

    def normalize_evidence(self, raw_item: dict[str, Any]) -> dict[str, Any]:
        """Normalize HackerRank badge/profile/challenge payload into Knowledge Mesh schema."""
        item_type = raw_item.get("type", "hackerrank_profile")
        data = raw_item.get("data", {})

        if item_type == "hackerrank_profile":
            return {
                "platform": self.platform_name,
                "external_id": f"hackerrank_profile_{data.get('username')}",
                "title": f"HackerRank Profile: {data.get('username')}",
                "evidence_type": "profile",
                "source_url": data.get("html_url"),
                "occurred_at": datetime.now().isoformat(),
                "raw_payload": data,
                "normalized_payload": {
                    "skills": ["Algorithms", "Problem Solving"],
                    "level": data.get("level", 1),
                    "total_solved": data.get("total_solved"),
                },
            }
        elif item_type == "hackerrank_challenge":
            name = data.get("name") or data.get("title", "HackerRank Challenge")
            slug = data.get("ch_slug") or data.get("slug", "challenge")
            url_path = data.get("url", f"/challenges/{slug}/problem")
            source_url = f"https://www.hackerrank.com{url_path}" if url_path.startswith("/") else url_path
            created_at = data.get("created_at") or datetime.now().isoformat()

            track = data.get("track") or {}
            track_name = track.get("track_name") or data.get("track_name", "")
            sub_name = track.get("name") or data.get("sub_name", "")

            skills = self._extract_challenge_skills(data)
            primary_topic = skills[0] if skills else (sub_name or track_name or "Problem Solving")

            return {
                "platform": self.platform_name,
                "external_id": f"hackerrank_challenge_{slug}",
                "title": f"HackerRank Challenge: {name} (Solved)",
                "evidence_type": "problem_submission",
                "source_url": source_url,
                "occurred_at": created_at,
                "raw_payload": data,
                "normalized_payload": {
                    "challenge_title": name,
                    "challenge_slug": slug,
                    "status": "Solved",
                    "solved": True,
                    "track": track_name,
                    "subdomain": sub_name,
                    "topic": primary_topic,
                    "skills": skills,
                },
            }
        else:
            badge_name = data.get("badge_name", "Skill Badge")
            stars = data.get("stars", 1)
            hatch = data.get("hatch_level", "Bronze")

            return {
                "platform": self.platform_name,
                "external_id": f"hackerrank_badge_{badge_name}_{stars}",
                "title": f"HackerRank Badge: {badge_name} ({stars} Stars - {hatch})",
                "evidence_type": "badge",
                "source_url": f"https://www.hackerrank.com/profile/{data.get('username', 'user')}",
                "occurred_at": datetime.now().isoformat(),
                "raw_payload": data,
                "normalized_payload": {
                    "badge_name": badge_name,
                    "stars": stars,
                    "hatch_level": hatch,
                    "solved": data.get("solved"),
                    "skills": [badge_name, "Problem Solving"],
                },
            }

