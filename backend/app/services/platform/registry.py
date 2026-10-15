"""Central Platform Registry & Capability Metadata Model."""

from typing import Any, Optional, Type
from app.services.platform.base import BasePlatformConnector


class PlatformCapability:
    PUBLIC_PROFILE = "public_profile"
    PUBLIC_ACTIVITY = "public_activity"
    PUBLIC_SUBMISSIONS = "public_submissions"
    PUBLIC_PROBLEM_HISTORY = "public_problem_history"
    PUBLIC_REPOSITORIES = "public_repositories"
    PUBLIC_SOURCE_CODE = "public_source_code"
    OAUTH_REQUIRED = "oauth_required"
    LIMITED_API = "limited_api"
    UNSUPPORTED = "unsupported"


class PlatformStatus:
    AVAILABLE = "AVAILABLE"
    OAUTH_REQUIRED = "OAUTH_REQUIRED"
    LIMITED = "LIMITED"
    PLANNED = "PLANNED"
    UNSUPPORTED = "UNSUPPORTED"
    RATE_LIMITED = "RATE_LIMITED"


class PlatformRegistryItem:
    """Descriptor object representing a registered developer platform."""

    def __init__(
        self,
        key: str,
        name: str,
        connector_class: Type[BasePlatformConnector],
        capabilities: list[str],
        status: str,
        auth_type: str = "username_public",
        data_scope_description: str = "",
        documentation_url: Optional[str] = None,
    ):
        self.key = key.lower()
        self.name = name
        self.connector_class = connector_class
        self.capabilities = capabilities
        self.status = status
        self.auth_type = auth_type
        self.data_scope_description = data_scope_description
        self.documentation_url = documentation_url

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "capabilities": self.capabilities,
            "status": self.status,
            "auth_type": self.auth_type,
            "data_scope_description": self.data_scope_description,
            "documentation_url": self.documentation_url,
        }


class PlatformRegistry:
    """Registry managing available developer platform connectors."""

    _registry: dict[str, PlatformRegistryItem] = {}

    @classmethod
    def register(cls, item: PlatformRegistryItem):
        cls._registry[item.key] = item

    @classmethod
    def get_item(cls, key: str) -> Optional[PlatformRegistryItem]:
        return cls._registry.get(key.lower())

    @classmethod
    def get_connector_instance(cls, key: str, auth_token: Optional[str] = None) -> Optional[BasePlatformConnector]:
        item = cls.get_item(key)
        if not item:
            return None
        return item.connector_class(auth_token=auth_token)

    @classmethod
    def list_items(cls) -> list[PlatformRegistryItem]:
        return list(cls._registry.values())

    @classmethod
    def platform_names(cls) -> list[str]:
        """Display names (as stored in PlatformConnection.platform), in registration order."""
        return [item.connector_class.platform_name for item in cls._registry.values()]
