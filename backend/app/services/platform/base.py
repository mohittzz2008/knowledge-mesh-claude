"""Abstract Base Class for Developer Platform Connectors."""

from abc import ABC, abstractmethod
from typing import Any, Optional


class BasePlatformConnector(ABC):
    """Abstract connector defining standard interface for developer evidence ingestion."""

    platform_name: str

    @abstractmethod
    async def validate_identity(self, identifier: str, auth_type: str = "username_public") -> bool:
        """Validate if the username or OAuth token corresponds to an active account."""
        pass

    @abstractmethod
    async def fetch_profile(self, identifier: str) -> Optional[dict[str, Any]]:
        """Fetch permitted developer profile statistics."""
        pass

    @abstractmethod
    async def fetch_evidence(self, identifier: str) -> list[dict[str, Any]]:
        """Fetch permitted evidence items (commits, solved problems, badges)."""
        pass

    @abstractmethod
    def normalize_evidence(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """Normalize raw platform data into standardized Knowledge Mesh evidence schema."""
        pass
