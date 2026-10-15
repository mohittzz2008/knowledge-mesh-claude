"""AtCoder Platform Connector."""

import json
import re
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

KENKOOOO_BASE = "https://kenkoooo.com/atcoder/atcoder-api"


class AtCoderConnector(BasePlatformConnector):
    """Integrates AtCoder identity, rating, and unique solved problems."""

    platform_name = "AtCoder"

    def __init__(
        self,
        auth_token: Optional[str] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        self.auth_token = auth_token
        self.transport = transport

    async def validate_identity(self, identifier: str, auth_type: str = "username_public") -> bool:
        """Validate an AtCoder username by checking the public profile."""
        handle = clean_handle(identifier)
        if not handle:
            return False

        url = f"https://atcoder.jp/users/{path_segment(handle)}"
        async with make_client(transport=self.transport) as client:
            try:
                res = await get(client, url, platform=self.platform_name)
                if res.status_code == 200:
                    html = res.text
                    # Ensure it's not a generic page or 404 page masked as 200
                    if "404 Not Found" in html or "User not found" in html:
                        return False
                    return True
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

    async def fetch_profile(self, identifier: str) -> Optional[dict[str, Any]]:
        """Fetch AtCoder profile data including rating from public HTML and Kenkoooo stats."""
        handle = clean_handle(identifier)
        if not handle:
            return None

        url = f"https://atcoder.jp/users/{path_segment(handle)}"
        async with make_client(transport=self.transport) as client:
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

            html = res.text
            if "404 Not Found" in html or "User not found" in html:
                return None

            current_rating = None
            highest_rating = None

            # Extract rank_history from the script payload
            match = re.search(r"var rank_history\s*=\s*(\[.*?\]);", html, re.DOTALL)
            if match:
                try:
                    history = json.loads(match.group(1))
                    if isinstance(history, list) and history:
                        ratings = [
                            h.get("Rating")
                            for h in history
                            if isinstance(h, dict) and h.get("Rating") is not None
                        ]
                        if ratings:
                            current_rating = ratings[-1]
                            highest_rating = max(ratings)
                except json.JSONDecodeError:
                    pass

            # Fallback to HTML table if rank_history was not present or empty
            if current_rating is None:
                table_rating_match = re.search(r'<th[^>]*>Rating</th>\s*<td>.*?(\d+)', html, re.DOTALL)
                if table_rating_match:
                    try:
                        current_rating = int(table_rating_match.group(1))
                    except ValueError:
                        pass
            if highest_rating is None:
                table_highest_match = re.search(r'<th[^>]*>Highest Rating</th>\s*<td>.*?(\d+)', html, re.DOTALL)
                if table_highest_match:
                    try:
                        highest_rating = int(table_highest_match.group(1))
                    except ValueError:
                        pass

            global_rank = None
            rank_match = re.search(r'<th[^>]*>Rank</th>\s*<td>\s*(\d+)', html)
            if rank_match:
                try:
                    global_rank = int(rank_match.group(1))
                except ValueError:
                    pass

            rated_matches = None
            matches_match = re.search(r'<th[^>]*>Rated Matches.*?</th>\s*<td>\s*(\d+)', html)
            if matches_match:
                try:
                    rated_matches = int(matches_match.group(1))
                except ValueError:
                    pass

            # Fetch solved count from Kenkoooo user_info
            total_solved = None
            try:
                k_url = f"{KENKOOOO_BASE}/v2/user_info?user={path_segment(handle)}"
                k_res = await client.get(k_url)
                if k_res.status_code == 200:
                    k_data = k_res.json()
                    if isinstance(k_data, dict):
                        raw_ac = k_data.get("accepted_count")
                        if raw_ac is not None:
                            try:
                                total_solved = int(raw_ac)
                            except (ValueError, TypeError):
                                total_solved = None
            except Exception:
                # Kenkoooo is third-party: if it fails during profile fetch, total_solved is None (not 0)
                total_solved = None

            return {
                "platform": self.platform_name,
                "username": handle,
                "handle": handle,
                "name": handle,
                "avatar_url": None,
                "html_url": url,
                "rating": current_rating,
                "current_rating": current_rating,
                "highest_rating": highest_rating,
                "maxRating": highest_rating,
                "rank": global_rank,
                "global_rank": global_rank,
                "rated_matches": rated_matches,
                "total_solved": total_solved,
            }

    async def fetch_evidence(self, identifier: str) -> list[dict[str, Any]]:
        """Fetch AtCoder submissions from AtCoderProblems API to calculate unique solved."""
        handle = clean_handle(identifier)
        if not handle:
            return []

        profile = await self.fetch_profile(handle)
        if not profile:
            return []

        async with make_client(transport=self.transport) as client:
            url = f"{KENKOOOO_BASE}/v3/user/submissions?user={path_segment(handle)}&from_second=0"
            try:
                res = await get(client, url, platform=self.platform_name)
            except (RateLimitedError, UpstreamUnavailableError):
                raise
            except Exception as err:
                raise UpstreamUnavailableError(
                    f"Could not reach AtCoderProblems: {err}",
                    platform=self.platform_name,
                ) from err

            if res.status_code != 200:
                raise UpstreamUnavailableError(
                    f"AtCoderProblems API unavailable: HTTP {res.status_code}",
                    platform=self.platform_name,
                )

            try:
                submissions = res.json()
            except Exception as err:
                raise UpstreamFormatError(
                    "Malformed response from AtCoderProblems",
                    platform=self.platform_name,
                ) from err

            if not isinstance(submissions, list):
                raise UpstreamFormatError(
                    "AtCoderProblems returned non-list submissions payload",
                    platform=self.platform_name,
                )

            solved_problem_ids = set()
            languages = set()
            total_submissions = len(submissions)

            for sub in submissions:
                if not isinstance(sub, dict):
                    continue
                if sub.get("result") == "AC":
                    pid = sub.get("problem_id")
                    if pid:
                        solved_problem_ids.add(pid)

                lang = sub.get("language", "")
                if lang:
                    # E.g. "C++14 (GCC 5.4.1)" -> "c++14"
                    base_lang = lang.split()[0].lower()
                    languages.add(base_lang)

            total_solved = profile.get("total_solved")
            if total_solved is None:
                total_solved = len(solved_problem_ids)

            return [{
                "type": "atcoder_profile_stats",
                "data": profile,
                "total_solved": total_solved,
                "total_submissions": total_submissions,
                "languages": sorted(list(languages)),
            }]

    def normalize_evidence(self, raw_item: dict[str, Any]) -> dict[str, Any]:
        """Normalize raw evidence into Knowledge Mesh schema."""
        item_type = raw_item.get("type")
        data = raw_item.get("data", {}) or {}

        if item_type == "atcoder_profile_stats":
            handle = data.get("username") or data.get("handle") or ""
            current_rating = (
                data.get("rating") if data.get("rating") is not None else data.get("current_rating")
            )
            highest_rating = (
                data.get("highest_rating")
                if data.get("highest_rating") is not None
                else data.get("maxRating")
            )

            total_solved = raw_item.get("total_solved")
            if total_solved is None:
                total_solved = data.get("total_solved")

            rating_str = f" (Rating: {current_rating})" if current_rating is not None else ""

            return {
                "platform": self.platform_name,
                "external_id": f"atcoder_profile_{handle.lower()}",
                "title": f"AtCoder Profile: {handle}{rating_str}",
                "evidence_type": "problem_solving_summary",
                "source_url": data.get("html_url") or f"https://atcoder.jp/users/{handle}",
                "occurred_at": datetime.now(timezone.utc).isoformat(),
                "raw_payload": raw_item,
                "normalized_payload": {
                    "rating": current_rating,
                    "maxRating": highest_rating,
                    "total_solved": total_solved,
                    "total_submissions": raw_item.get("total_submissions"),
                    "skills": raw_item.get("languages", []),
                },
            }

        return {}
