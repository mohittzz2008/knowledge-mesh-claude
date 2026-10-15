"""Pydantic schemas for Platform Connectors, Central Registry, and Identity Sync."""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class PlatformValidateRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=128, description="Target platform username")


class PlatformValidateResponse(BaseModel):
    platform: str
    username: str
    valid: bool
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    public_repos: Optional[int] = None
    followers: Optional[int] = None
    total_solved: Optional[int] = None
    detail: Optional[str] = None


class PlatformSyncRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=128, description="Target platform username")
    auth_type: str = Field("username_public", description="'username_public' or 'oauth_token'")
    auth_token: Optional[str] = Field(None, description="Optional OAuth or access token")


class PlatformSyncResponse(BaseModel):
    platform_connection_id: str
    platform: str
    username: str
    connected: bool
    synced_evidence_count: int
    updated_evidence_count: int = 0
    profile_summary: dict[str, Any]
    last_synced_at: datetime
    message: str


class PlatformRegistryItemSchema(BaseModel):
    key: str
    name: str
    capabilities: list[str]
    status: str
    auth_type: str
    data_scope_description: str
    documentation_url: Optional[str] = None
    connected: bool = False
    connected_username: Optional[str] = None
    last_synced_at: Optional[datetime] = None
