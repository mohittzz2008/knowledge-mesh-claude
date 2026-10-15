"""CodeChef Platform Connector using public profile parsing."""

from datetime import datetime, timezone
import re
from html import unescape
from typing import Any, Optional
import httpx

from app.services.platform.base import BasePlatformConnector
from app.services.platform.http_util import clean_handle, get, make_client, path_segment

CODECHEF_BASE_URL = "https://www.codechef.com"
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def extract_codechef_solved_problems(html: str) -> list[dict[str, str]]:
    """Extract solved problem titles and codes from CodeChef user profile HTML."""
    solved_items = []
    seen_ids = set()

    # Search for section.problems-solved
    match = re.search(r'<section\s+class="[^"]*problems-solved[^"]*"[^>]*>(.*?)</section>', html, re.DOTALL | re.IGNORECASE)
    section_content = match.group(1) if match else html

    # Strategy 1: Extract problem titles from <span style="font-size: 12px">
    span_matches = re.findall(r'<span\s+style=["\']font-size:\s*12px;?["\']\s*;?>\s*(.*?)\s*</span>', section_content, re.IGNORECASE)
    for raw_title in span_matches:
        cleaned_title = unescape(re.sub(r'<[^>]+>', '', raw_title)).replace('\xa0', ' ').replace('&nbsp;', ' ').strip()
        if cleaned_title and len(cleaned_title) > 1 and cleaned_title.lower() not in seen_ids:
            seen_ids.add(cleaned_title.lower())
            code = re.sub(r'[^A-Za-z0-9_]+', '', cleaned_title.upper()) or "PROBLEM"
            solved_items.append({
                "problem_title": cleaned_title,
                "problem_code": code,
            })

    # Strategy 2: Extract problem codes/links from <a href=".../problems/CODE"> or /status/CODE
    anchor_matches = re.findall(
        r'<a\s+[^>]*href=["\'](?:https?://[^/]+)?(?:/[^/]+)?/(?:problems|status)/([A-Za-z0-9_]+)[,\'"][^>]*>(.*?)</a>',
        section_content,
        re.IGNORECASE | re.DOTALL,
    )
    for code, inner_text in anchor_matches:
        code_upper = code.upper()
        if code_upper in ("PRACTICE", "EASY", "MEDIUM", "HARD", "SCHOOL", "CHALLENGE", "RATINGS", "STATUS"):
            continue
        cleaned_text = unescape(re.sub(r'<[^>]+>', '', inner_text)).strip() or code_upper
        if code_upper.lower() not in seen_ids:
            seen_ids.add(code_upper.lower())
            solved_items.append({
                "problem_title": cleaned_text,
                "problem_code": code_upper,
            })

    return solved_items


class CodeChefConnector(BasePlatformConnector):
    """CodeChef Connector fetching profile telemetry, star ratings, and solved problems."""

    platform_name = "CodeChef"

    def __init__(
        self,
        auth_token: Optional[str] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        self.auth_token = auth_token
        self.headers = dict(DEFAULT_HEADERS)
        self._transport = transport
        self._html_cache: dict[str, Optional[str]] = {}

    async def _fetch_html(self, handle: str) -> Optional[str]:
        """Public profile HTML, or None when the page does not exist. Cached per instance.

        Network failures, 429 and 5xx raise typed connector errors (so the API can say
        "CodeChef is unavailable" instead of wrongly reporting the user as not found).
        """
        key = handle.lower()
        if key in self._html_cache:
            return self._html_cache[key]

        async with make_client(self._transport, headers=self.headers) as client:
            res = await get(
                client,
                f"{CODECHEF_BASE_URL}/users/{path_segment(handle)}",
                platform=self.platform_name,
            )
        html = res.text if res.status_code == 200 else None
        self._html_cache[key] = html
        return html

    @staticmethod
    def _looks_like_profile(html: str, handle: str) -> bool:
        """A real profile page, not a 200-status 'not found' / redirect-to-home page.

        Requires a profile-specific marker. Merely containing the username somewhere in the
        page is not enough (the requested name can appear in an error page's URL or text).
        """
        markers = ("rating-header", "user-details", "rating-number", "problems-solved", "user-profile")
        if any(m in html for m in markers):
            return True
        title = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        return bool(title and handle.lower() in title.group(1).lower())

    async def validate_identity(self, identifier: str, auth_type: str = "username_public") -> bool:
        """Validate that a public CodeChef profile exists for this username."""
        handle = clean_handle(identifier)
        if not handle:
            return False
        html = await self._fetch_html(handle)
        return html is not None and self._looks_like_profile(html, handle)

    async def fetch_profile(self, identifier: str) -> Optional[dict[str, Any]]:
        """Fetch CodeChef profile statistics, rating, highest rating, star tier, and solved problems."""
        handle = clean_handle(identifier)
        if not handle:
            return None

        username = handle
        url = f"{CODECHEF_BASE_URL}/users/{path_segment(username)}"

        html = await self._fetch_html(handle)
        if html is None or not self._looks_like_profile(html, handle):
            return None

        # Extract rating number
        rating = None
        rating_match = re.search(r'rating-number.*?>\s*(\d+)\s*<', html)
        if rating_match:
            try:
                rating = int(rating_match.group(1))
            except ValueError:
                rating = None

        # Extract highest rating
        highest_rating = rating
        highest_match = re.search(r'Highest Rating\s*(\d+)', html, re.IGNORECASE)
        if highest_match:
            try:
                parsed_highest = int(highest_match.group(1))
                if parsed_highest > 0:
                    highest_rating = max(rating or 0, parsed_highest)
                else:
                    highest_rating = rating
            except ValueError:
                highest_rating = rating
        elif rating is not None:
            highest_rating = rating

        # Extract star rating (e.g. 1★, 2★, 3★, 4★, 5★, 6★, 7★)
        stars = None
        star_block_match = re.search(r'class=["\']rating-star["\'][^>]*>(.*?)</div>', html, re.DOTALL | re.IGNORECASE)
        if star_block_match:
            star_block = star_block_match.group(1)
            digit_match = re.search(r'([1-7])\s*(?:★|\*|&#9733;)', star_block)
            if digit_match:
                stars = f"{digit_match.group(1)}★"
            else:
                glyph_count = len(re.findall(r'&#9733;|★', star_block))
                if glyph_count > 1:
                    stars = f"{glyph_count}★"
                elif star_block.strip() and "★" in star_block:
                    stars = star_block.strip()

        # Fallback to rating brackets only if user has an active rating and no explicit star markup was parsed
        if not stars and rating and rating > 0:
            if rating >= 2500:
                stars = "7★"
            elif rating >= 2200:
                stars = "6★"
            elif rating >= 2000:
                stars = "5★"
            elif rating >= 1800:
                stars = "4★"
            elif rating >= 1600:
                stars = "3★"
            elif rating >= 1400:
                stars = "2★"
            else:
                stars = "1★"

        # Extract global rank (check sidebar, contest graph, or inline text; avoid false zeros)
        global_rank = None
        gr_match = re.search(r'<strong>\s*(\d+)\s*</strong>\s*</a>\s*Global Rank', html, re.IGNORECASE)
        if not gr_match:
            gr_match = re.search(r'<strong[^>]*class=[\'"]global-rank[\'"][^>]*>\s*(\d+)\s*</strong>', html, re.IGNORECASE)
        if not gr_match:
            gr_match = re.search(r'Global Rank:?.*?>\s*(\d+)\s*<', html, re.IGNORECASE)
        if gr_match:
            try:
                global_rank = int(gr_match.group(1))
            except ValueError:
                global_rank = None

        # Extract country rank (sidebar or inline; avoid false zeros)
        country_rank = None
        cr_match = re.search(r'<strong>\s*(\d+)\s*</strong>\s*</a>\s*Country Rank', html, re.IGNORECASE)
        if not cr_match:
            cr_match = re.search(r'<strong[^>]*class=[\'"]country-rank[\'"][^>]*>\s*(\d+)\s*</strong>', html, re.IGNORECASE)
        if not cr_match:
            cr_match = re.search(r'Country Rank:?.*?>\s*(\d+)\s*<', html, re.IGNORECASE)
        if cr_match:
            try:
                country_rank = int(cr_match.group(1))
            except ValueError:
                country_rank = None

        # Extract contest participation
        contests_participated = None
        cp_match = re.search(r'(?:No\.\s*of\s*)?Contests\s+Participated:\s*<b>\s*(\d+)\s*</b>', html, re.IGNORECASE)
        if not cp_match:
            cp_match = re.search(r'<h3>\s*Contests\s*\(\s*(\d+)\s*\)\s*</h3>', html, re.IGNORECASE)
        if cp_match:
            try:
                contests_participated = int(cp_match.group(1))
            except ValueError:
                contests_participated = None

        # Extract solved problems from HTML
        solved_problems = extract_codechef_solved_problems(html)
        solved_codes = [p["problem_code"] for p in solved_problems]

        # Extract total solved count header if present.
        # Note: Profile HTML only embeds a partial subset of solved problems (e.g. recent contests),
        # so len(solved_problems) cannot be trusted as a complete lifetime total if the explicit
        # 'Total Problems Solved: N' header is missing.
        header_solved_match = re.search(r'Total Problems Solved:\s*(\d+)', html, re.IGNORECASE)
        if header_solved_match:
            try:
                total_solved = int(header_solved_match.group(1))
            except ValueError:
                total_solved = None
        elif solved_problems:
            total_solved = None  # Unknown: partial list present but explicit total missing
        else:
            total_solved = 0  # Verified genuine zero

        # Extract name
        real_name = username
        name_match = re.search(r'h1 class="h2-style">\s*(.*?)\s*<', html)
        if name_match:
            real_name = name_match.group(1).strip() or username

        return {
            "platform": self.platform_name,
            "username": username,
            "name": real_name,
            "avatar_url": "https://cdn.codechef.com/sites/all/themes/abstrack/images/user-crop.png",
            "html_url": url,
            "rating": rating,
            "highest_rating": highest_rating,
            "stars": stars,
            "global_rank": global_rank,
            "country_rank": country_rank,
            "contests_participated": contests_participated,
            "solved_problems": solved_problems,
            "solved_codes": solved_codes,
            "total_solved": total_solved,
        }

    async def fetch_evidence(self, identifier: str) -> list[dict[str, Any]]:
        """Fetch CodeChef profile, star badge, and solved problem evidence."""
        username = identifier.strip()
        profile = await self.fetch_profile(username)

        raw_items = []
        if profile:
            raw_items.append({
                "type": "codechef_profile_stats",
                "data": profile,
            })

            if profile.get("stars"):
                raw_items.append({
                    "type": "codechef_star_badge",
                    "data": {
                        "username": username,
                        "badge_name": f"CodeChef {profile.get('stars')} Coder",
                        "stars": profile.get("stars"),
                        "rating": profile.get("rating", 0),
                    },
                })

            for prob in profile.get("solved_problems", []):
                raw_items.append({
                    "type": "codechef_solved_problem",
                    "data": {
                        "username": username,
                        "problem_code": prob["problem_code"],
                        "problem_title": prob["problem_title"],
                    },
                })

        return raw_items

    def normalize_evidence(self, raw_item: dict[str, Any]) -> dict[str, Any]:
        """Normalize raw CodeChef item into Knowledge Mesh schema."""
        item_type = raw_item.get("type", "codechef_profile_stats")
        data = raw_item.get("data", {})

        if item_type == "codechef_profile_stats":
            rating = data.get("rating")
            rating_display = f" (Rating: {rating})" if rating is not None else ""
            total_solved = data.get("total_solved", 0)
            skills = (
                ["Algorithms", "Data Structures", "Problem Solving", "Competitive Programming"]
                if ((rating and rating > 0) or total_solved > 0)
                else []
            )
            return {
                "platform": self.platform_name,
                "external_id": f"codechef_profile_{data.get('username')}",
                "title": f"CodeChef Profile: {data.get('username')}{rating_display}",
                "evidence_type": "problem_solving_summary",
                "source_url": data.get("html_url"),
                "occurred_at": datetime.now(timezone.utc).isoformat(),
                "raw_payload": data,
                "normalized_payload": {
                    "rating": rating,
                    "highest_rating": data.get("highest_rating", rating),
                    "stars": data.get("stars"),
                    "global_rank": data.get("global_rank"),
                    "country_rank": data.get("country_rank"),
                    "contests_participated": data.get("contests_participated"),
                    "total_solved": total_solved,
                    "skills": skills,
                },
            }
        elif item_type == "codechef_star_badge":
            badge_name = data.get("badge_name", "CodeChef Coder")
            stars_str = str(data.get("stars", "1"))
            stars_num = int(stars_str[0]) if stars_str[0].isdigit() else 1
            return {
                "platform": self.platform_name,
                "external_id": f"codechef_badge_{data.get('username')}_{stars_num}",
                "title": f"CodeChef Badge: {badge_name}",
                "evidence_type": "badge",
                "source_url": f"https://www.codechef.com/users/{data.get('username')}",
                "occurred_at": None,  # CodeChef exposes no award date; never fabricated
                "raw_payload": data,
                "normalized_payload": {
                    "badge_name": badge_name,
                    "stars": stars_num,
                    "rating": data.get("rating", 0),
                    "skills": ["Competitive Programming", "Algorithms"],
                },
            }

        else:
            code = data.get("problem_code", "UNKNOWN")
            title = data.get("problem_title") or f"CodeChef Problem: {code}"
            return {
                "platform": self.platform_name,
                "external_id": f"codechef_prob_{data.get('username')}_{code}",
                "title": f"CodeChef Solved Challenge: {title}",
                "evidence_type": "problem_submission",
                "source_url": f"https://www.codechef.com/problems/{code}",
                "occurred_at": None,  # CodeChef exposes no solve date; never fabricated
                "raw_payload": data,
                "normalized_payload": {
                    "problem_code": code,
                    "problem_title": title,
                    "status": "Solved",
                    "passed": True,
                    "skills": ["Math", "Algorithms", "Problem Solving"],
                },
            }
