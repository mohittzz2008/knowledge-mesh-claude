"""LeetCode Platform Connector using GraphQL API Ingestion."""

from datetime import datetime
from typing import Any, Optional
import httpx

from app.services.platform.base import BasePlatformConnector

LEETCODE_GRAPHQL_URL = "https://leetcode.com/graphql"
DEFAULT_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "KnowledgeMesh-Bot/1.0",
}


class LeetCodeConnector(BasePlatformConnector):
    """LeetCode Connector fetching profile telemetry via GraphQL."""

    platform_name = "LeetCode"

    def __init__(self, auth_token: Optional[str] = None):
        self.auth_token = auth_token
        self.headers = dict(DEFAULT_HEADERS)

    async def validate_identity(self, identifier: str, auth_type: str = "username_public") -> bool:
        """Validate if a public LeetCode username exists via official GraphQL endpoint."""
        if not identifier or not identifier.strip():
            return False

        username = identifier.strip()
        query = """
        query getUserProfile($username: String!) {
          matchedUser(username: $username) {
            username
          }
        }
        """

        print(f"[EXTERNAL REQUEST]\nplatform=LeetCode\nusername={username}\nendpoint={LEETCODE_GRAPHQL_URL}\nHTTP status=PENDING")

        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=5.0) as client:
                res = await client.post(LEETCODE_GRAPHQL_URL, json={"query": query, "variables": {"username": username}})
                print(f"[EXTERNAL REQUEST]\nplatform=LeetCode\nusername={username}\nendpoint={LEETCODE_GRAPHQL_URL}\nHTTP status={res.status_code}")
                if res.status_code == 200:
                    data = res.json()
                    user_data = data.get("data", {}).get("matchedUser")
                    # STEP 7: Verify matchedUser is non-null and returned username matches requested username (case-insensitive)
                    if user_data and user_data.get("username"):
                        returned_user = user_data.get("username")
                        matched = returned_user.lower() == username.lower()
                        print(
                            f"[EXTERNAL RESPONSE]\nplatform=LeetCode\nrequested_username={username}\n"
                            f"returned_username={returned_user}\nmatched_identity={matched}\ndata_count=1 if matched else 0"
                        )
                        return matched
                print(f"[EXTERNAL RESPONSE]\nplatform=LeetCode\nrequested_username={username}\nreturned_username=None\nmatched_identity=False\ndata_count=0")
        except (httpx.RequestError, httpx.TimeoutException) as err:
            print(f"[EXTERNAL RESPONSE]\nplatform=LeetCode\nrequested_username={username}\nerror={err}")
            pass
        return False

    async def fetch_profile(self, identifier: str) -> Optional[dict[str, Any]]:
        """Fetch LeetCode profile & problem solving statistics via GraphQL."""
        username = identifier.strip()
        query = """
        query getUserStats($username: String!) {
          matchedUser(username: $username) {
            username
            githubUrl
            profile {
              realName
              userAvatar
              ranking
            }
            submitStatsGlobal {
              acSubmissionNum {
                difficulty
                count
              }
            }
          }
          userContestRanking(username: $username) {
            attendedContestsCount
            rating
            globalRanking
            totalParticipants
            topPercentage
          }
        }
        """

        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=5.0) as client:
                res = await client.post(LEETCODE_GRAPHQL_URL, json={"query": query, "variables": {"username": username}})
                if res.status_code == 200:
                    res_json = res.json() if isinstance(res.json(), dict) else {}
                    payload = res_json.get("data")
                    if not isinstance(payload, dict):
                        return None
                    user_data = payload.get("matchedUser")
                    if user_data:
                        returned_username = user_data.get("username", "")
                        if returned_username.lower() != username.lower():
                            return None

                        stats = user_data.get("submitStatsGlobal", {}).get("acSubmissionNum", [])
                        total_solved = next((s["count"] for s in stats if s.get("difficulty") == "All"), 0)
                        easy_solved = next((s["count"] for s in stats if s.get("difficulty") == "Easy"), 0)
                        medium_solved = next((s["count"] for s in stats if s.get("difficulty") == "Medium"), 0)
                        hard_solved = next((s["count"] for s in stats if s.get("difficulty") == "Hard"), 0)

                        prof = user_data.get("profile", {}) or {}

                        contest_data = payload.get("userContestRanking")
                        contest_rating = None
                        contest_ranking = None
                        contest_attended = None
                        contest_top_percentage = None

                        if isinstance(contest_data, dict):
                            raw_rating = contest_data.get("rating")
                            if raw_rating is not None:
                                try:
                                    contest_rating = round(float(raw_rating), 2)
                                except (ValueError, TypeError):
                                    contest_rating = None

                            raw_ranking = contest_data.get("globalRanking")
                            if raw_ranking is not None:
                                try:
                                    contest_ranking = int(raw_ranking)
                                except (ValueError, TypeError):
                                    contest_ranking = None

                            raw_attended = contest_data.get("attendedContestsCount")
                            if raw_attended is not None:
                                try:
                                    contest_attended = int(raw_attended)
                                except (ValueError, TypeError):
                                    contest_attended = None

                            raw_top_pct = contest_data.get("topPercentage")
                            if raw_top_pct is not None:
                                try:
                                    contest_top_percentage = round(float(raw_top_pct), 2)
                                except (ValueError, TypeError):
                                    contest_top_percentage = None

                        return {
                            "platform": self.platform_name,
                            "username": user_data.get("username"),
                            "name": prof.get("realName") or user_data.get("username"),
                            "avatar_url": prof.get("userAvatar"),
                            "html_url": f"https://leetcode.com/{user_data.get('username')}/",
                            "ranking": prof.get("ranking", 0),
                            "total_solved": total_solved,
                            "easy_solved": easy_solved,
                            "medium_solved": medium_solved,
                            "hard_solved": hard_solved,
                            "contest_rating": contest_rating,
                            "contest_ranking": contest_ranking,
                            "contest_attended": contest_attended,
                            "contest_top_percentage": contest_top_percentage,
                            "rating": contest_rating,
                        }
        except (httpx.RequestError, httpx.TimeoutException):
            pass
        return None

    async def fetch_recent_submissions(self, username: str, limit: int = 15) -> list[dict[str, Any]]:
        """Fetch recent public LeetCode problem submissions."""
        query = """
        query getRecentSubmissions($username: String!, $limit: Int!) {
          recentSubmissionList(username: $username, limit: $limit) {
            title
            titleSlug
            timestamp
            statusDisplay
            lang
          }
        }
        """

        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=5.0) as client:
                res = await client.post(LEETCODE_GRAPHQL_URL, json={"query": query, "variables": {"username": username, "limit": limit}})
                if res.status_code == 200:
                    return res.json().get("data", {}).get("recentSubmissionList", [])
        except (httpx.RequestError, httpx.TimeoutException):
            pass
        return []

    async def fetch_skill_stats(self, username: str) -> list[dict[str, Any]]:
        """Fetch LeetCode topic/tag problem counts via GraphQL."""
        query = """
        query skillStats($username: String!) {
          matchedUser(username: $username) {
            tagProblemCounts {
              fundamental { tagName tagSlug problemsSolved }
              intermediate { tagName tagSlug problemsSolved }
              advanced { tagName tagSlug problemsSolved }
            }
          }
        }
        """

        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=5.0) as client:
                res = await client.post(LEETCODE_GRAPHQL_URL, json={"query": query, "variables": {"username": username}})
                if res.status_code == 200:
                    counts = res.json().get("data", {}).get("matchedUser", {}).get("tagProblemCounts") or {}
                    tags = []
                    for cat in ["fundamental", "intermediate", "advanced"]:
                        for t in (counts.get(cat) or []):
                            if t.get("problemsSolved", 0) > 0:
                                t["username"] = username
                                tags.append(t)
                    return tags
        except (httpx.RequestError, httpx.TimeoutException):
            pass
        return []

    async def fetch_evidence(self, identifier: str) -> list[dict[str, Any]]:
        """Fetch LeetCode problem telemetry evidence."""
        username = identifier.strip()
        profile = await self.fetch_profile(username)
        submissions = await self.fetch_recent_submissions(username)

        raw_items = []
        if profile:
            raw_items.append({
                "type": "leetcode_profile_stats",
                "data": profile,
            })

            # Fetch skill stats only if account has >0 solved problems
            if profile.get("total_solved", 0) > 0:
                skill_tags = await self.fetch_skill_stats(username)
                for tag in skill_tags:
                    raw_items.append({
                        "type": "leetcode_tag_stat",
                        "data": tag,
                    })

        for sub in submissions:
            raw_items.append({
                "type": "leetcode_submission",
                "data": sub,
            })

        return raw_items

    def normalize_evidence(self, raw_item: dict[str, Any]) -> dict[str, Any]:
        """Normalize LeetCode submission payload into Knowledge Mesh schema."""
        item_type = raw_item.get("type", "leetcode_profile_stats")
        data = raw_item.get("data", {})

        if item_type == "leetcode_profile_stats":
            total = data.get("total_solved", 0)
            norm_payload = {
                "total_solved": total,
                "easy_solved": data.get("easy_solved", 0),
                "medium_solved": data.get("medium_solved", 0),
                "hard_solved": data.get("hard_solved", 0),
                "ranking": data.get("ranking", 0),
                "contest_rating": data.get("contest_rating"),
                "contest_ranking": data.get("contest_ranking"),
                "contest_attended": data.get("contest_attended"),
                "contest_top_percentage": data.get("contest_top_percentage"),
                "rating": data.get("contest_rating"),
                "skills": ["Algorithms", "Data Structures", "Problem Solving"] if total > 0 else [],
            }
            return {
                "platform": self.platform_name,
                "external_id": f"leetcode_profile_{data.get('username')}",
                "title": f"LeetCode Profile: {data.get('username')} ({total} Solved)",
                "evidence_type": "problem_solving_summary",
                "source_url": data.get("html_url"),
                "occurred_at": datetime.now().isoformat(),
                "raw_payload": data,
                "normalized_payload": norm_payload,
            }
        elif item_type == "leetcode_tag_stat":
            tag_name = data.get("tagName", "Problem Tag")
            solved_count = data.get("problemsSolved", 0)
            tag_slug = data.get("tagSlug", "tag")
            return {
                "platform": self.platform_name,
                "external_id": f"leetcode_tag_{data.get('username')}_{tag_slug}",
                "title": f"LeetCode Topic Mastery: {tag_name} ({solved_count} Solved)",
                "evidence_type": "topic_statistics",
                "source_url": f"https://leetcode.com/tag/{tag_slug}/",
                "occurred_at": datetime.now().isoformat(),
                "raw_payload": data,
                "normalized_payload": {
                    "tag_name": tag_name,
                    "problems_solved": solved_count,
                    "skills": [tag_name, "Algorithms"],
                },
            }
        else:
            title = data.get("title", "LeetCode Problem")
            slug = data.get("titleSlug", "problem")
            status = data.get("statusDisplay", "Accepted")
            lang = data.get("lang", "Python")
            ts = data.get("timestamp")

            occurred_at = datetime.fromtimestamp(int(ts)).isoformat() if ts else datetime.now().isoformat()
            is_accepted = status.lower() == "accepted"

            return {
                "platform": self.platform_name,
                "external_id": f"leetcode_sub_{slug}_{ts}",
                "title": f"LeetCode Submission: {title} ({status})",
                "evidence_type": "problem_submission",
                "source_url": f"https://leetcode.com/problems/{slug}/",
                "occurred_at": occurred_at,
                "raw_payload": data,
                "normalized_payload": {
                    "problem_title": title,
                    "title_slug": slug,
                    "status": status,
                    "language": lang,
                    "passed": is_accepted,
                    "skills": [lang, "Algorithms", "Problem Solving"],
                },
            }
