"""GitHub Connector Implementation using HTTPX REST Client."""

import base64
import os
import re
from typing import Any, Optional
import httpx

from app.services.platform.base import BasePlatformConnector
from app.services.platform.errors import (
    IncompleteHistoryError,
    RateLimitedError,
    UpstreamFormatError,
    UpstreamUnavailableError,
)
from app.services.platform.http_util import make_client, path_segment

GITHUB_API_BASE = "https://api.github.com"
DEFAULT_HEADERS = {
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "KnowledgeMesh-Bot/1.0 (+https://github.com/mohittzz2008/knowledge-mesh)",
}

# GitHub username: 1-39 alphanumeric chars or single internal hyphens (no leading/trailing/consecutive hyphens)
_GITHUB_HANDLE_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$")
MAX_REPOS_PAGES = 10
MAX_EVENTS_PAGES = 3


def clean_github_handle(identifier: Optional[str]) -> Optional[str]:
    """Validate and return clean GitHub username, or None if invalid syntax."""
    if not identifier:
        return None
    handle = identifier.strip()
    return handle if _GITHUB_HANDLE_RE.match(handle) else None


async def _github_get(
    client: httpx.AsyncClient,
    url: str,
) -> httpx.Response:
    """GET with GitHub-specific rate limit and error mapping."""
    try:
        response = await client.get(url)
    except httpx.TimeoutException as err:
        raise UpstreamUnavailableError("GitHub timed out.", platform="GitHub") from err
    except httpx.RequestError as err:
        raise UpstreamUnavailableError(
            f"Could not reach GitHub: {err.__class__.__name__}.", platform="GitHub"
        ) from err

    # Check for HTTP 429 or HTTP 403 rate-limit response
    if response.status_code == 429 or (
        response.status_code == 403
        and (
            response.headers.get("x-ratelimit-remaining") == "0"
            or "rate limit" in response.text.lower()
        )
    ):
        reset_time = response.headers.get("x-ratelimit-reset", "unknown")
        raise RateLimitedError(
            f"GitHub API rate limited. Resets at {reset_time}.",
            platform="GitHub",
        )

    if response.status_code >= 500:
        raise UpstreamUnavailableError(
            f"GitHub is temporarily unavailable (HTTP {response.status_code}).",
            platform="GitHub",
        )

    return response


class GitHubConnector(BasePlatformConnector):
    """GitHub Platform Connector performing real REST API Ingestion."""

    platform_name = "GitHub"

    def __init__(
        self,
        auth_token: Optional[str] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        self.auth_token = auth_token or os.getenv("GITHUB_TOKEN")
        self.headers = dict(DEFAULT_HEADERS)
        if self.auth_token:
            self.headers["Authorization"] = f"token {self.auth_token}"
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        return make_client(transport=self._transport, headers=self.headers)

    async def validate_identity(self, identifier: str, auth_type: str = "username_public") -> bool:
        """Validate whether a public GitHub username exists via official GitHub API."""
        handle = clean_github_handle(identifier)
        if not handle:
            return False

        url = f"{GITHUB_API_BASE}/users/{path_segment(handle)}"
        async with self._client() as client:
            res = await _github_get(client, url)
            if res.status_code == 200:
                try:
                    data = res.json()
                    login = data.get("login")
                    return bool(login and login.lower() == handle.lower())
                except (ValueError, TypeError):
                    return False
            if res.status_code == 404:
                return False
            return False

    async def fetch_profile(self, identifier: str) -> Optional[dict[str, Any]]:
        """Fetch developer profile statistics from GitHub API."""
        handle = clean_github_handle(identifier)
        if not handle:
            return None

        url = f"{GITHUB_API_BASE}/users/{path_segment(handle)}"
        async with self._client() as client:
            res = await _github_get(client, url)
            if res.status_code == 404:
                return None
            if res.status_code != 200:
                return None

            try:
                data = res.json()
            except (ValueError, TypeError) as err:
                raise UpstreamFormatError(
                    f"Invalid JSON received from GitHub: {err}",
                    platform=self.platform_name,
                ) from err

            if not isinstance(data, dict):
                raise UpstreamFormatError(
                    "GitHub user response is not a dict.",
                    platform=self.platform_name,
                )

            login = data.get("login")
            if not login or login.lower() != handle.lower():
                return None

            return {
                "platform": self.platform_name,
                "username": login,
                "name": data.get("name"),
                "avatar_url": data.get("avatar_url"),
                "html_url": data.get("html_url"),
                "bio": data.get("bio"),
                "company": data.get("company"),
                "location": data.get("location"),
                "blog": data.get("blog"),
                "twitter_username": data.get("twitter_username"),
                "public_repos": data.get("public_repos", 0),
                "public_gists": data.get("public_gists", 0),
                "followers": data.get("followers", 0),
                "following": data.get("following", 0),
                "created_at": data.get("created_at"),
                "updated_at": data.get("updated_at"),
            }

    async def fetch_repos(self, username: str, limit: int = 100) -> list[dict[str, Any]]:
        """Fetch developer public repositories strictly owned by username."""
        handle = clean_github_handle(username)
        if not handle:
            return []

        owned_repos: list[dict[str, Any]] = []
        seen_repo_ids: set[int | str] = set()
        page = 1
        history_exhausted = False

        async with self._client() as client:
            while page <= MAX_REPOS_PAGES:
                url = f"{GITHUB_API_BASE}/users/{path_segment(handle)}/repos?type=owner&sort=updated&per_page={limit}&page={page}"
                res = await _github_get(client, url)

                if res.status_code == 200:
                    try:
                        page_repos = res.json()
                    except (ValueError, TypeError) as err:
                        raise UpstreamFormatError(
                            f"Invalid JSON received from GitHub repos: {err}",
                            platform=self.platform_name,
                        ) from err

                    if not isinstance(page_repos, list):
                        raise UpstreamFormatError(
                            "GitHub repos response is not a list.",
                            platform=self.platform_name,
                        )

                    if not page_repos:
                        history_exhausted = True
                        break

                    for r in page_repos:
                        if not isinstance(r, dict):
                            continue
                        if r.get("owner", {}).get("login", "").lower() == handle.lower():
                            repo_id = r.get("id")
                            if repo_id not in seen_repo_ids:
                                seen_repo_ids.add(repo_id)
                                owned_repos.append(r)

                    if len(page_repos) < limit:
                        history_exhausted = True
                        break
                    page += 1
                elif res.status_code == 404:
                    history_exhausted = True
                    if page == 1:
                        return []
                    break
                else:
                    raise UpstreamUnavailableError(
                        f"GitHub repos failed with status {res.status_code}",
                        platform=self.platform_name,
                    )

        if not history_exhausted and page > MAX_REPOS_PAGES:
            raise IncompleteHistoryError(
                f"GitHub repository history exceeded safety limit ({MAX_REPOS_PAGES} pages) "
                f"without reaching end of repositories. Aborting to avoid returning incomplete repository list.",
                platform=self.platform_name,
            )

        return owned_repos

    async def fetch_events(self, username: str, limit: int = 100) -> list[dict[str, Any]]:
        """Fetch public developer activity events (pushes, PRs, issue activities)."""
        handle = clean_github_handle(username)
        if not handle:
            return []

        events: list[dict[str, Any]] = []
        seen_event_ids: set[str] = set()
        page = 1

        async with self._client() as client:
            while page <= MAX_EVENTS_PAGES:
                url = f"{GITHUB_API_BASE}/users/{path_segment(handle)}/events/public?per_page={limit}&page={page}"
                res = await _github_get(client, url)

                if res.status_code == 200:
                    try:
                        page_events = res.json()
                    except (ValueError, TypeError) as err:
                        raise UpstreamFormatError(
                            f"Invalid JSON received from GitHub events: {err}",
                            platform=self.platform_name,
                        ) from err

                    if not isinstance(page_events, list):
                        raise UpstreamFormatError(
                            "GitHub events response is not a list.",
                            platform=self.platform_name,
                        )

                    if not page_events:
                        break

                    for ev in page_events:
                        if not isinstance(ev, dict):
                            continue
                        ev_id = str(ev.get("id"))
                        if ev_id not in seen_event_ids:
                            seen_event_ids.add(ev_id)
                            events.append(ev)

                    if len(page_events) < limit:
                        break
                    page += 1
                elif res.status_code == 404:
                    break
                else:
                    raise UpstreamUnavailableError(
                        f"GitHub events failed with status {res.status_code}",
                        platform=self.platform_name,
                    )

        return events

    async def fetch_file_content(self, owner: str, repo: str, path: str) -> Optional[dict[str, Any]]:
        """Retrieve accessible source file content from a repository."""
        clean_owner = clean_github_handle(owner)
        if not clean_owner or not repo or not path:
            return None

        url = f"{GITHUB_API_BASE}/repos/{path_segment(clean_owner)}/{path_segment(repo)}/contents/{path}"
        async with self._client() as client:
            res = await _github_get(client, url)
            if res.status_code != 200:
                return None

            try:
                data = res.json()
            except (ValueError, TypeError):
                return None

            content_b64 = data.get("content", "")
            encoding = data.get("encoding", "")

            decoded_code = None
            if encoding == "base64" and content_b64:
                try:
                    decoded_code = base64.b64decode(content_b64).decode("utf-8")
                except Exception:
                    decoded_code = None

            return {
                "path": data.get("path"),
                "sha": data.get("sha"),
                "size": data.get("size"),
                "html_url": data.get("html_url"),
                "code_content": decoded_code,
                "download_url": data.get("download_url"),
            }

    async def fetch_evidence(self, identifier: str) -> list[dict[str, Any]]:
        """Orchestrate public GitHub repository & event data collection."""
        handle = clean_github_handle(identifier)
        if not handle:
            return []

        profile = await self.fetch_profile(handle)
        repos = await self.fetch_repos(handle)
        events = await self.fetch_events(handle)

        evidence_raw_items: list[dict[str, Any]] = []

        # 1. Profile statistics evidence item
        if profile:
            evidence_raw_items.append({
                "type": "profile_stats",
                "data": profile,
            })

        # 2. Verified owned repositories
        for repo in repos:
            repo_owner = repo.get("owner", {}).get("login", "")
            if repo_owner.lower() == handle.lower():
                evidence_raw_items.append({
                    "type": "repository",
                    "data": repo,
                })

        # 3. Activity events
        for ev in events:
            evidence_raw_items.append({
                "type": "activity",
                "data": ev,
            })

        return evidence_raw_items

    def normalize_evidence(self, raw_item: dict[str, Any]) -> dict[str, Any]:
        """Normalize GitHub event, repository, or profile payload to Knowledge Mesh standard schema."""
        item_type = raw_item.get("type", "repository")
        data = raw_item.get("data", {})
        if not isinstance(data, dict):
            return {}

        if item_type == "profile_stats":
            username = data.get("username") or data.get("login") or "Unknown"
            name = data.get("name")
            title_display = f"{name} (@{username})" if name else f"@{username}"
            public_repos = data.get("public_repos", 0)
            followers = data.get("followers", 0)
            following = data.get("following", 0)
            created_at = data.get("created_at")
            updated_at = data.get("updated_at")

            return {
                "platform": self.platform_name,
                "external_id": f"github_profile_{username.lower()}",
                "title": f"GitHub Profile: {title_display}",
                "evidence_type": "profile",
                "source_url": data.get("html_url"),
                "occurred_at": updated_at or created_at,
                "raw_payload": data,
                "normalized_payload": {
                    "username": username,
                    "name": name,
                    "public_repos": public_repos,
                    "followers": followers,
                    "following": following,
                    "bio": data.get("bio"),
                    "company": data.get("company"),
                    "location": data.get("location"),
                    "skills": ["Git", "Open Source", "Software Development"],
                },
            }

        elif item_type == "repository":
            repo_name = data.get("name", "Unknown Repo")
            full_name = data.get("full_name", repo_name)
            language = data.get("language")
            topics = data.get("topics", [])
            stars = data.get("stargazers_count", 0)
            html_url = data.get("html_url")
            updated_at_str = data.get("updated_at")

            skills = []
            if language:
                skills.append(language)
            if isinstance(topics, list):
                for t in topics:
                    if isinstance(t, str):
                        skills.append(t.capitalize())
            if not skills:
                skills = ["Git", "Software Development"]

            raw_id = str(data.get("id"))
            external_id = raw_id if raw_id.startswith("github_repo_") else f"github_repo_{raw_id}"

            return {
                "platform": self.platform_name,
                "external_id": external_id,
                "title": f"Repository: {full_name}",
                "evidence_type": "repository",
                "source_url": html_url,
                "occurred_at": updated_at_str,
                "raw_payload": data,
                "normalized_payload": {
                    "repository_name": repo_name,
                    "full_name": full_name,
                    "primary_language": language,
                    "topics": topics,
                    "stars": stars,
                    "skills": list(dict.fromkeys(skills)),
                    "description": data.get("description"),
                },
            }

        elif item_type == "activity":
            event_type = data.get("type", "Event")
            repo_name = data.get("repo", {}).get("name", "GitHub Event")
            created_at_str = data.get("created_at")

            action_desc = "Activity Event"
            skills = ["Git"]

            if event_type == "PushEvent":
                commits_count = len(data.get("payload", {}).get("commits", []))
                action_desc = f"Pushed {commits_count} commit(s) to {repo_name}"
                skills.append("Version Control")
            elif event_type == "PullRequestEvent":
                pr_action = data.get("payload", {}).get("action", "opened")
                action_desc = f"{pr_action.capitalize()} PR in {repo_name}"
                skills.append("Code Review")
            elif event_type == "CreateEvent":
                ref_type = data.get("payload", {}).get("ref_type", "repository")
                action_desc = f"Created {ref_type} in {repo_name}"
            else:
                action_desc = f"{event_type} on {repo_name}"

            raw_ev_id = str(data.get("id"))
            external_id = raw_ev_id if raw_ev_id.startswith("github_event_") else f"github_event_{raw_ev_id}"

            return {
                "platform": self.platform_name,
                "external_id": external_id,
                "title": action_desc,
                "evidence_type": "commit" if event_type == "PushEvent" else "activity",
                "source_url": f"https://github.com/{repo_name}",
                "occurred_at": created_at_str,
                "raw_payload": data,
                "normalized_payload": {
                    "event_type": event_type,
                    "repository": repo_name,
                    "skills": list(dict.fromkeys(skills)),
                },
            }

        elif item_type == "code_file":
            path = data.get("path", "")
            raw_sha = str(data.get("sha"))
            external_id = raw_sha if raw_sha.startswith("github_file_") else f"github_file_{raw_sha}"
            return {
                "platform": self.platform_name,
                "external_id": external_id,
                "title": f"Source File: {path}",
                "evidence_type": "code_file",
                "source_url": data.get("html_url"),
                "occurred_at": None,
                "raw_payload": data,
                "normalized_payload": {
                    "file_path": path,
                    "size_bytes": data.get("size", 0),
                    "code_content": data.get("code_content"),
                    "skills": ["Source Code Analysis"],
                },
            }

        # Default fallback
        raw_art_id = str(data.get("id", "0"))
        external_id = raw_art_id if raw_art_id.startswith("github_artifact_") else f"github_artifact_{raw_art_id}"
        return {
            "platform": self.platform_name,
            "external_id": external_id,
            "title": "GitHub Development Artifact",
            "evidence_type": "activity",
            "source_url": None,
            "occurred_at": None,
            "raw_payload": data,
            "normalized_payload": {
                "skills": ["Software Engineering"],
            },
        }

