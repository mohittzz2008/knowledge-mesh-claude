"""Unit and Integration tests for Unified Developer Profile & Cross-Platform Intelligence."""

import pytest
from app.services.mesh.unified_profile import UnifiedProfileService
from app.services.mesh.concept_extractor import ConceptExtractorService


def test_unified_profile_service(db_session):
    service = UnifiedProfileService()
    profile = service.get_unified_profile("test_user_id", db_session)
    assert "overall_skill_score" in profile
    assert "total_evidence_count" in profile
    assert "platform_counts" in profile
    assert "connected_platforms" in profile


def test_cross_platform_concept_extractor(db_session):
    extractor = ConceptExtractorService()
    assessments = extractor.extract_and_assess_user_skills("test_user_id", db_session)
    assert len(assessments) >= 10
