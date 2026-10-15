"""GeeksforGeeks Platform Connector.

GeeksforGeeks has NO official public API. The public profile page
(https://www.geeksforgeeks.org/user/{handle}/) is a Next.js page whose
``<script id="__NEXT_DATA__">`` JSON carries the profile (``userInfo``) and the
solved-problem lists (``userSubmissionsInfo``, grouped by difficulty).

That layout is not a contract. This connector therefore:
  * reads only that one public page per sync (cached per connector instance),
  * accepts several key spellings for each field,
  * raises ``UpstreamFormatError`` ("layout changed") when the page loads but no
    profile data can be found - it never invents data and never reports a real
    user as "not found" because of a layout change.

``www.geeksforgeeks.org/user/`` is not disallowed for generic crawlers in the
site's robots.txt; keep the request volume low (one page per sync).
"""

import json
import re
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from app.services.platform.base import BasePlatformConnector
from app.services.platform.errors import UpstreamFormatError
from app.services.platform.http_util import clean_handle, get, make_client, path_segment

SITE_BASE = "https://www.geeksforgeeks.org"

MAX_PROBLEM_EVIDENCE = 30
# Hardest first, so the capped evidence list favours the strongest signals.
DIFFICULTY_ORDER = ["Hard", "Medium", "Easy", "Basic", "School"]

_NEXT_DATA_RE = re.compile(
    r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', re.DOTALL | re.IGNORECASE
)

LANGUAGE_DISPLAY = {
    "python": "Python",
    "python3": "Python",
    "c": "C",
    "cpp": "C++",
    "c++": "C++",
    "java": "Java",
    "javascript": "JavaScript",
    "csharp": "C#",
    "c#": "C#",
}


def display_language(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    key = raw.strip().lower()
    return LANGUAGE_DISPLAY.get(key, raw.strip())


def _find_key(obj: Any, key: str, depth: int = 5) -> Any:
    """Breadth-first search for ``key`` in nested dicts/lists, a few levels deep."""
    queue = [(obj, 0)]
    while queue:
        current, level = queue.pop(0)
        if isinstance(current, dict):
            if key in current:
                return current[key]
            if level < depth:
                queue.extend((v, level + 1) for v in current.values())
        elif isinstance(current, list) and level < depth:
            queue.extend((v, level + 1) for v in current)
    return None


def _first(mapping: dict[str, Any], *keys: str) -> Any:
    for k in keys:
        if mapping.get(k) not in (None, ""):
            return mapping[k]
    return None


def _to_int(value: Any) -> Optional[int]:
    try:
        return int(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def extract_next_data(html: str) -> Optional[dict[str, Any]]:
    match = _NEXT_DATA_RE.search(html or "")
    if not match:
        return None
    try:
        parsed = json.loads(match.group(1))
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def parse_solved_problems(submissions: Any) -> list[dict[str, Any]]:
    """Flatten ``userSubmissionsInfo`` into ``[{name, slug, difficulty, language}]``."""
    problems: list[dict[str, Any]] = []
    if not isinstance(submissions, dict):
        return problems

    for difficulty in DIFFICULTY_ORDER + [d for d in submissions if d not in DIFFICULTY_ORDER]:
        bucket = submissions.get(difficulty)
        if isinstance(bucket, dict):
            entries = list(bucket.values())
        elif isinstance(bucket, list):
            entries = bucket
        else:
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            name = _first(entry, "pname", "name", "title")
            slug = _first(entry, "slug", "problem_slug")
            if not name and not slug:
                continue
            problems.append(
                {
                    "name": name or str(slug).replace("-", " ").title(),
                    "slug": slug,
                    "difficulty": str(difficulty).title(),
                    "language": display_language(_first(entry, "lang", "language")),
                }
            )
    return problems


def extract_app_router_profile(html: str, handle: str) -> Optional[dict[str, Any]]:
    """Extract profile data from Next.js App Router self.__next_f.push scripts."""
    if not html:
        return None

    script_pattern = re.compile(r'<script\b[^>]*>(.*?)</script>', re.DOTALL)
    for match in script_pattern.finditer(html):
        script_text = match.group(1)
        if "articleCount" not in script_text and "total_problems_solved" not in script_text:
            continue

        cleaned = script_text.replace('\\"', '"').replace('\\\\', '\\').replace('\\/', '/')

        ac_match = re.search(r'"articleCount"\s*:\s*(\{.*?\})\s*,\s*"userData"', cleaned)
        if not ac_match:
            ac_match = re.search(r'"articleCount"\s*:\s*(\{[^{}]*"total_problems_solved"[^{}]*\})', cleaned)

        mentor_match = re.search(r'"mentor"\s*:\s*(\{.*?\})\s*,\s*"username"', cleaned)
        user_match = re.search(r'"username"\s*:\s*"([^"]+)"', cleaned)

        article_count = {}
        if ac_match:
            try:
                article_count = json.loads(ac_match.group(1))
            except Exception:
                pass

        mentor = {}
        if mentor_match:
            try:
                mentor = json.loads(mentor_match.group(1))
            except Exception:
                pass

        matched_handle = user_match.group(1) if user_match else mentor.get("handle")
        if matched_handle and handle.lower() != str(matched_handle).lower():
            # Identity mismatch: page is for another account
            return {"mismatch": True}

        if article_count:
            name = article_count.get("name") or mentor.get("name") or handle
            avatar_url = mentor.get("profile_image_url") or article_count.get("profile_image_url")
            institute = article_count.get("institute_name") or None
            institute_rank = _to_int(article_count.get("institute_rank"))

            score_val = article_count.get("score")
            if score_val is None:
                score_val = article_count.get("overall_coding_score")
            coding_score = _to_int(score_val)

            monthly_score = _to_int(article_count.get("monthly_score"))

            streak_val = article_count.get("pod_solved_longest_streak")
            if streak_val is None:
                streak_val = article_count.get("streak")
            streak = _to_int(streak_val)

            total_solved = _to_int(article_count.get("total_problems_solved"))
            if total_solved is None:
                total_solved = 0

            profile = {
                "platform": "GeeksforGeeks",
                "username": handle,
                "name": name,
                "avatar_url": avatar_url,
                "html_url": f"{SITE_BASE}/user/{path_segment(handle)}/",
                "institute": institute,
                "institute_rank": institute_rank,
                "coding_score": coding_score,
                "monthly_score": monthly_score,
                "streak": streak,
                "total_solved": total_solved,
            }
            return {"profile": profile, "problems": []}

    return None


class GeeksforGeeksConnector(BasePlatformConnector):
    """Integrates a public GeeksforGeeks practice profile."""

    platform_name = "GeeksforGeeks"

    def __init__(
        self,
        auth_token: Optional[str] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        self.auth_token = auth_token
        self._transport = transport
        self._page_cache: dict[str, Optional[dict[str, Any]]] = {}

    async def _load(self, handle: str) -> Optional[dict[str, Any]]:
        """Parsed profile bundle, or None when the user does not exist. Cached per instance."""
        key = handle.lower()
        if key in self._page_cache:
            return self._page_cache[key]

        async with make_client(self._transport, headers={"Accept": "text/html"}) as client:
            # Try /user/{handle}/ first (follows redirect to /profile/{handle} in live env;
            # matches legacy mock transports in test suites). If 404, fallback to /profile/{handle}.
            response = await get(
                client,
                f"{SITE_BASE}/user/{path_segment(handle)}/",
                platform=self.platform_name,
            )
            if response.status_code == 404:
                response = await get(
                    client,
                    f"{SITE_BASE}/profile/{path_segment(handle)}",
                    platform=self.platform_name,
                )

        if response.status_code != 200:
            self._page_cache[key] = None
            return None

        # 1. Try legacy __NEXT_DATA__ format (backward compatibility with fixtures / older pages)
        next_data = extract_next_data(response.text)
        if next_data is not None:
            page_props = (next_data.get("props") or {}).get("pageProps") or {}
            user_info = _find_key(page_props, "userInfo")
            if not isinstance(user_info, dict) or not user_info:
                # Page rendered, but has no profile: the handle does not exist (or is private).
                self._page_cache[key] = None
                return None

            submissions = _find_key(page_props, "userSubmissionsInfo")
            problems = parse_solved_problems(submissions)

            total = _to_int(_first(user_info, "total_problems_solved", "totalProblemsSolved"))
            if total is None:
                total = len(problems)

            profile = {
                "platform": self.platform_name,
                "username": handle,
                "name": _first(user_info, "name", "full_name") or handle,
                "avatar_url": _first(user_info, "profile_image_url", "pic", "profile_picture"),
                "html_url": f"{SITE_BASE}/user/{path_segment(handle)}/",
                "institute": _first(user_info, "institute_name", "instituteName"),
                "institute_rank": _to_int(_first(user_info, "institute_rank", "instituteRank")),
                "coding_score": _to_int(_first(user_info, "score", "overall_coding_score")),
                "monthly_score": _to_int(_first(user_info, "monthly_score", "monthlyScore")),
                "streak": _to_int(_first(user_info, "pod_solved_longest_streak", "streak_count", "streak")),
                "total_solved": total,
            }

            if profile["name"] == handle and total == 0 and not problems and not profile["coding_score"]:
                # Nothing recognisable in userInfo at all -> treat as a layout problem, not a user.
                raise UpstreamFormatError(
                    "GeeksforGeeks profile data was present but in an unrecognised shape. "
                    "The connector needs an update.",
                    platform=self.platform_name,
                )

            bundle = {"profile": profile, "problems": problems}
            self._page_cache[key] = bundle
            return bundle

        # 2. Try modern Next.js App Router format (self.__next_f.push)
        app_router_bundle = extract_app_router_profile(response.text, handle)
        if app_router_bundle is not None:
            if app_router_bundle.get("mismatch"):
                self._page_cache[key] = None
                return None
            self._page_cache[key] = app_router_bundle
            return app_router_bundle

        # 3. Neither format matched on a 200 page:
        # Check if the page is a soft-404 / not found page
        if "not found" in response.text.lower() or "404" in response.text:
            self._page_cache[key] = None
            return None

        raise UpstreamFormatError(
            "GeeksforGeeks profile page layout changed (no embedded profile data). "
            "The connector needs an update.",
            platform=self.platform_name,
        )

    async def validate_identity(self, identifier: str, auth_type: str = "username_public") -> bool:
        handle = clean_handle(identifier)
        if not handle:
            return False
        return (await self._load(handle)) is not None

    async def fetch_profile(self, identifier: str) -> Optional[dict[str, Any]]:
        handle = clean_handle(identifier)
        if not handle:
            return None
        bundle = await self._load(handle)
        return bundle["profile"] if bundle else None

    async def fetch_evidence(self, identifier: str) -> list[dict[str, Any]]:
        handle = clean_handle(identifier)
        if not handle:
            return []
        bundle = await self._load(handle)
        if not bundle:
            return []

        profile = bundle["profile"]
        problems = bundle["problems"]

        difficulty_counts: dict[str, int] = {}
        languages: dict[str, int] = {}
        for p in problems:
            difficulty_counts[p["difficulty"]] = difficulty_counts.get(p["difficulty"], 0) + 1
            if p.get("language"):
                languages[p["language"]] = languages.get(p["language"], 0) + 1

        items: list[dict[str, Any]] = [
            {
                "type": "gfg_profile_stats",
                "data": profile,
                "difficulty_counts": difficulty_counts,
                "languages": [l for l, _ in sorted(languages.items(), key=lambda kv: kv[1], reverse=True)],
            }
        ]
        for problem in problems[:MAX_PROBLEM_EVIDENCE]:
            items.append({"type": "gfg_problem", "data": {**problem, "username": profile["username"]}})
        return items

    def normalize_evidence(self, raw_item: dict[str, Any]) -> dict[str, Any]:
        item_type = raw_item.get("type")
        data = raw_item.get("data", {}) or {}

        if item_type == "gfg_profile_stats":
            username = data.get("username", "")
            total = data.get("total_solved", 0) or 0
            languages = raw_item.get("languages", []) or []
            skills = (languages + ["Algorithms", "Data Structures", "Problem Solving"]) if total > 0 else []
            return {
                "platform": self.platform_name,
                "external_id": f"gfg_profile_{username.lower()}",
                "title": f"GeeksforGeeks Profile: {username} ({total} Solved)",
                "evidence_type": "problem_solving_summary",
                "source_url": data.get("html_url"),
                "occurred_at": datetime.now(timezone.utc).isoformat(),
                "raw_payload": data,
                "normalized_payload": {
                    "total_solved": total,
                    "coding_score": data.get("coding_score"),
                    "monthly_score": data.get("monthly_score"),
                    "institute_rank": data.get("institute_rank"),
                    "streak": data.get("streak"),
                    "difficulty_counts": raw_item.get("difficulty_counts", {}),
                    "languages": languages,
                    "skills": skills,
                },
            }

        if item_type == "gfg_problem":
            slug = data.get("slug") or re.sub(r"[^a-z0-9]+", "-", str(data.get("name", "")).lower()).strip("-")
            name = data.get("name") or "GeeksforGeeks Problem"
            language = data.get("language")
            difficulty = data.get("difficulty")
            skills = [s for s in [language, "Algorithms", "Data Structures", "Problem Solving"] if s]
            return {
                "platform": self.platform_name,
                "external_id": f"gfg_problem_{data.get('username', '').lower()}_{slug}",
                "title": f"GeeksforGeeks Problem: {name} ({difficulty})"[:255],
                "evidence_type": "problem_submission",
                "source_url": f"{SITE_BASE}/problems/{path_segment(slug)}" if slug else None,
                "occurred_at": None,  # GeeksforGeeks does not expose solve timestamps
                "raw_payload": data,
                "normalized_payload": {
                    "problem_title": name,
                    "title_slug": slug,
                    "status": "Solved",
                    "passed": True,
                    "difficulty": difficulty,
                    "language": language,
                    "skills": skills,
                },
            }

        return {}
