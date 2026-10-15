"""Codeforces Platform Connector."""

import asyncio
from datetime import datetime
from typing import Any, Optional
import httpx

from app.services.platform.base import BasePlatformConnector
from app.services.platform.errors import RateLimitedError, UpstreamUnavailableError
from app.services.platform.http_util import clean_handle, get, make_client, path_segment

CODEFORCES_API_URL = "https://codeforces.com/api"
DEFAULT_HEADERS = {
    "User-Agent": "KnowledgeMesh-Bot/1.0",
}


class IncompleteHistoryError(UpstreamUnavailableError):
    """Raised when lifetime submission history cannot be fully retrieved (e.g. max_pages hard cap reached)."""
    pass


class CodeforcesConnector(BasePlatformConnector):
    """Codeforces Connector fetching profile telemetry via official REST API."""

    platform_name = "Codeforces"

    def __init__(
        self,
        auth_token: Optional[str] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
        page_delay: Optional[float] = None,
        max_retries: int = 3,
        base_backoff: Optional[float] = None,
    ):
        self.auth_token = auth_token
        self.transport = transport
        self.headers = dict(DEFAULT_HEADERS)
        # Official Codeforces guidance: max 5 requests/sec. Default 0.25s delay in live mode, 0.0s in tests.
        self.page_delay = page_delay if page_delay is not None else (0.0 if transport is not None else 0.25)
        self.max_retries = max_retries
        self.base_backoff = base_backoff if base_backoff is not None else (0.0 if transport is not None else 0.5)

    @staticmethod
    def _problem_key(problem: dict[str, Any]) -> Optional[str]:
        """Generate a stable, unique problem identifier.

        Codeforces problems are primarily identified by contestId + problem index
        (e.g., '123_A'). For gym or ancient problemsets without contestId, fall back
        to problemsetName + index, or problem name.
        """
        contest_id = problem.get("contestId")
        index = problem.get("index")
        if contest_id is not None and index:
            return f"{contest_id}_{index}"
        problemset_name = problem.get("problemsetName")
        if problemset_name and index:
            return f"{problemset_name}_{index}"
        name = problem.get("name")
        if name:
            return f"name_{name}"
        return None

    async def _request_with_retry(self, client: httpx.AsyncClient, url: str) -> httpx.Response:
        """Execute GET with bounded exponential backoff for transient 429, 5xx, timeouts, and API limit errors."""
        last_exception = None
        for attempt in range(self.max_retries + 1):
            try:
                res = await get(client, url, platform=self.platform_name)

                # Check if Codeforces returned 200 or 400 with API-level call limit exceeded
                if res.status_code in (200, 400):
                    try:
                        data = res.json()
                        comment = str(data.get("comment", "")).lower()
                        if "limit exceeded" in comment:
                            if attempt < self.max_retries:
                                delay = self.base_backoff * (2 ** attempt)
                                if delay > 0:
                                    await asyncio.sleep(delay)
                                continue
                            raise RateLimitedError(
                                f"Codeforces rate limit reached: {data.get('comment')}",
                                platform=self.platform_name,
                            )
                    except ValueError:
                        pass
                return res

            except RateLimitedError as err:
                last_exception = err
                if attempt < self.max_retries:
                    delay = self.base_backoff * (2 ** attempt)
                    if delay > 0:
                        await asyncio.sleep(delay)
                    continue
                raise

            except UpstreamUnavailableError as err:
                last_exception = err
                if attempt < self.max_retries:
                    delay = self.base_backoff * (2 ** attempt)
                    if delay > 0:
                        await asyncio.sleep(delay)
                    continue
                raise

        if last_exception:
            raise last_exception
        raise UpstreamUnavailableError(f"Could not reach {self.platform_name}.", platform=self.platform_name)

    async def validate_identity(self, identifier: str, auth_type: str = "username_public") -> bool:
        """Validate if a public Codeforces username exists via official API."""
        handle = clean_handle(identifier)
        if not handle:
            return False

        url = f"{CODEFORCES_API_URL}/user.info?handles={path_segment(handle)}"

        async with make_client(transport=self.transport, headers=self.headers) as client:
            res = await self._request_with_retry(client, url)
            if res.status_code == 200:
                data = res.json()
                if data.get("status") == "OK":
                    result = data.get("result", [])
                    if result:
                        returned_user = result[0].get("handle", "")
                        return returned_user.lower() == handle.lower()
            elif res.status_code == 400:
                data = res.json()
                comment = data.get("comment", "")
                if "not found" in comment.lower():
                    return False
                raise UpstreamUnavailableError(
                    f"Codeforces API error: {comment}", platform=self.platform_name
                )
            elif res.status_code == 404:
                return False
        return False

    async def fetch_unique_solved_problems(
        self, username: str, page_size: int = 1000, max_pages: int = 200
    ) -> set[str]:
        """Paginate through all public submissions and return deduplicated accepted problem keys.

        Guarantees:
        1. Does not cap at 1,000 submissions; paginates through full lifetime history.
        2. Detects repeated pages and terminates safely to prevent infinite loops.
        3. Problem keys are stable (contestId + index).
        4. Strict check: counts problem only when verdict is genuinely 'OK'.
        5. Raises IncompleteHistoryError if max_pages is reached without establishing end of history.
        6. Implements polite inter-request delays and bounded retries with exponential backoff.
        7. Raises on upstream failure to avoid returning partial/misleading solved counts.
        """
        handle = clean_handle(username)
        if not handle:
            return set()

        from_index = 1
        seen_submission_ids: set[int] = set()
        unique_solved: set[str] = set()
        history_exhausted = False

        async with make_client(transport=self.transport, headers=self.headers) as client:
            for page_num in range(1, max_pages + 1):
                url = (
                    f"{CODEFORCES_API_URL}/user.status?"
                    f"handle={path_segment(handle)}&from={from_index}&count={page_size}"
                )
                res = await self._request_with_retry(client, url)

                if res.status_code == 200:
                    data = res.json()
                    if data.get("status") == "OK":
                        subs = data.get("result", [])
                        if not subs:
                            # Normal termination: empty page established end of history
                            history_exhausted = True
                            break

                        page_sub_ids = [s.get("id") for s in subs if s.get("id") is not None]
                        # Safe termination on repeated submissions or all-seen page
                        if page_sub_ids and all(sid in seen_submission_ids for sid in page_sub_ids):
                            history_exhausted = True
                            break

                        for s in subs:
                            sid = s.get("id")
                            if sid is not None:
                                seen_submission_ids.add(sid)

                            # Only verdict == "OK" counts as genuinely accepted
                            if s.get("verdict") == "OK":
                                problem = s.get("problem", {})
                                pkey = self._problem_key(problem)
                                if pkey:
                                    unique_solved.add(pkey)

                        if len(subs) < page_size:
                            # Normal termination: short final page established end of history
                            history_exhausted = True
                            break

                        from_index += len(subs)

                        # Respect rate limiting delay between consecutive pages
                        if self.page_delay > 0:
                            await asyncio.sleep(self.page_delay)

                    elif data.get("status") == "FAILED":
                        comment = data.get("comment", "")
                        if "not found" in comment.lower():
                            history_exhausted = True
                            break
                        raise UpstreamUnavailableError(
                            f"Codeforces API error: {comment}", platform=self.platform_name
                        )
                elif res.status_code == 400:
                    comment = res.json().get("comment", "")
                    if "not found" in comment.lower():
                        history_exhausted = True
                        break
                    raise UpstreamUnavailableError(
                        f"Codeforces API error: {comment}", platform=self.platform_name
                    )
                elif res.status_code == 404:
                    history_exhausted = True
                    break
                else:
                    raise UpstreamUnavailableError(
                        f"Codeforces API returned HTTP {res.status_code}",
                        platform=self.platform_name,
                    )

        if not history_exhausted:
            raise IncompleteHistoryError(
                f"Codeforces submission history exceeded maximum pagination limit ({max_pages} pages) "
                f"without reaching end of history. Aborting to avoid returning incomplete lifetime solved count.",
                platform=self.platform_name,
            )

        return unique_solved

    async def fetch_profile(self, identifier: str) -> Optional[dict[str, Any]]:
        """Fetch Codeforces profile & rating via official API."""
        handle = clean_handle(identifier)
        if not handle:
            return None

        url = f"{CODEFORCES_API_URL}/user.info?handles={path_segment(handle)}"

        async with make_client(transport=self.transport, headers=self.headers) as client:
            res = await self._request_with_retry(client, url)
            if res.status_code == 200:
                data = res.json()
                if data.get("status") == "OK" and data.get("result"):
                    user_data = data.get("result")[0]
                    returned_username = user_data.get("handle", "")
                    if returned_username.lower() != handle.lower():
                        return None

                    # Paginate all submissions to calculate true lifetime total_solved
                    unique_solved = await self.fetch_unique_solved_problems(returned_username)
                    total_solved = len(unique_solved)

                    return {
                        "platform": self.platform_name,
                        "username": returned_username,
                        "name": f"{user_data.get('firstName', '')} {user_data.get('lastName', '')}".strip()
                        or returned_username,
                        "avatar_url": user_data.get("titlePhoto") or user_data.get("avatar"),
                        "html_url": f"https://codeforces.com/profile/{returned_username}",
                        "rating": user_data.get("rating", 0),
                        "rank": user_data.get("rank", "unrated"),
                        "maxRating": user_data.get("maxRating", 0),
                        "contribution": user_data.get("contribution", 0),
                        "total_solved": total_solved,
                    }
            elif res.status_code == 400:
                data = res.json()
                comment = data.get("comment", "")
                if "not found" in comment.lower():
                    return None
                raise UpstreamUnavailableError(
                    f"Codeforces API error: {comment}", platform=self.platform_name
                )
            elif res.status_code == 404:
                return None
        return None

    async def fetch_recent_submissions(
        self, username: str, count: int = 100
    ) -> list[dict[str, Any]]:
        """Fetch recent public Codeforces problem submissions."""
        handle = clean_handle(username)
        if not handle:
            return []

        url = f"{CODEFORCES_API_URL}/user.status?handle={path_segment(handle)}&from=1&count={count}"

        async with make_client(transport=self.transport, headers=self.headers) as client:
            res = await self._request_with_retry(client, url)
            if res.status_code == 200:
                data = res.json()
                if data.get("status") == "OK":
                    return data.get("result", [])
            elif res.status_code in (400, 404):
                return []
        return []

    async def fetch_rating_history(self, username: str) -> list[dict[str, Any]]:
        """Fetch Codeforces contest rating history."""
        handle = clean_handle(username)
        if not handle:
            return []

        url = f"{CODEFORCES_API_URL}/user.rating?handle={path_segment(handle)}"

        async with make_client(transport=self.transport, headers=self.headers) as client:
            res = await self._request_with_retry(client, url)
            if res.status_code == 200:
                data = res.json()
                if data.get("status") == "OK":
                    return data.get("result", [])
            elif res.status_code in (400, 404):
                return []
        return []

    async def fetch_evidence(self, identifier: str) -> list[dict[str, Any]]:
        """Fetch Codeforces problem telemetry evidence."""
        handle = clean_handle(identifier)
        if not handle:
            return []

        profile = await self.fetch_profile(handle)
        submissions = await self.fetch_recent_submissions(handle)
        ratings = await self.fetch_rating_history(handle)

        raw_items = []
        if profile:
            raw_items.append({
                "type": "codeforces_profile_stats",
                "data": profile,
            })

        for sub in submissions:
            sub_copy = dict(sub)
            sub_copy["username"] = handle
            raw_items.append({
                "type": "codeforces_submission",
                "data": sub_copy,
            })

        for rating in ratings:
            rating_copy = dict(rating)
            rating_copy["username"] = handle
            raw_items.append({
                "type": "codeforces_rating_change",
                "data": rating_copy,
            })

        return raw_items

    def normalize_evidence(self, raw_item: dict[str, Any]) -> dict[str, Any]:
        """Normalize Codeforces payload into Knowledge Mesh schema."""
        item_type = raw_item.get("type", "codeforces_profile_stats")
        data = raw_item.get("data", {})

        if item_type == "codeforces_profile_stats":
            rating = data.get("rating", 0)
            return {
                "platform": self.platform_name,
                "external_id": f"codeforces_profile_{data.get('username')}",
                "title": f"Codeforces Profile: {data.get('username')} (Rating: {rating})",
                "evidence_type": "problem_solving_summary",
                "source_url": data.get("html_url"),
                "occurred_at": datetime.now().isoformat(),
                "raw_payload": data,
                "normalized_payload": {
                    "rating": rating,
                    "rank": data.get("rank"),
                    "maxRating": data.get("maxRating"),
                    "total_solved": data.get("total_solved"),
                    "skills": (
                        ["Algorithms", "Problem Solving", "Competitive Programming"]
                        if rating > 0
                        else []
                    ),
                },
            }
        elif item_type == "codeforces_rating_change":
            contest_name = data.get("contestName", "Codeforces Contest")
            contest_id = data.get("contestId")
            rank = data.get("rank", 0)
            new_rating = data.get("newRating", 0)
            old_rating = data.get("oldRating", 0)
            ts = data.get("ratingUpdateTimeSeconds")
            occurred_at = (
                datetime.fromtimestamp(int(ts)).isoformat() if ts else datetime.now().isoformat()
            )

            return {
                "platform": self.platform_name,
                "external_id": f"codeforces_rating_{data.get('username')}_{contest_id}_{ts}",
                "title": f"Codeforces Contest: {contest_name}",
                "evidence_type": "contest_performance",
                "source_url": f"https://codeforces.com/contest/{contest_id}",
                "occurred_at": occurred_at,
                "raw_payload": data,
                "normalized_payload": {
                    "contest_name": contest_name,
                    "rank": rank,
                    "old_rating": old_rating,
                    "new_rating": new_rating,
                    "rating_change": new_rating - old_rating,
                    "skills": ["Competitive Programming", "Algorithms"],
                },
            }
        else:
            problem = data.get("problem", {})
            title = problem.get("name", "Codeforces Problem")
            contest_id = problem.get("contestId")
            index = problem.get("index", "")
            status = data.get("verdict", "UNKNOWN")
            lang = data.get("programmingLanguage", "C++")
            ts = data.get("creationTimeSeconds")

            occurred_at = (
                datetime.fromtimestamp(int(ts)).isoformat() if ts else datetime.now().isoformat()
            )
            is_accepted = str(status).upper() == "OK"

            # Combine language and problem tags into skills
            skills = [lang, "Algorithms", "Problem Solving"]
            if problem.get("tags"):
                skills.extend([tag.title() for tag in problem.get("tags")])

            source_url = (
                f"https://codeforces.com/contest/{contest_id}/problem/{index}"
                if contest_id
                else "https://codeforces.com/problemset"
            )

            return {
                "platform": self.platform_name,
                "external_id": f"codeforces_sub_{data.get('id')}",
                "title": f"Codeforces Submission: {title} ({status})",
                "evidence_type": "problem_submission",
                "source_url": source_url,
                "occurred_at": occurred_at,
                "raw_payload": data,
                "normalized_payload": {
                    "problem_title": title,
                    "contest_id": contest_id,
                    "problem_index": index,
                    "status": status,
                    "language": lang,
                    "passed": is_accepted,
                    "skills": sorted(list(set(skills))),
                },
            }
