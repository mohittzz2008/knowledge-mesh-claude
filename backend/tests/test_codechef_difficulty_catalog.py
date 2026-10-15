"""Tests for expanded CodeChef practice problem difficulty catalog."""

import pytest
from app.services.recommendations.problem_matcher import CONTROLLED_PRACTICE_PROBLEMS


def test_codechef_difficulty_catalog():
    # Filter CodeChef entries
    cc_problems = [p for p in CONTROLLED_PRACTICE_PROBLEMS if p.get("platform") == "CodeChef"]
    
    assert len(cc_problems) > 2, "CodeChef catalog should contain expanded entries"

    easy_probs = [p for p in cc_problems if p.get("difficulty") == "Easy"]
    medium_probs = [p for p in cc_problems if p.get("difficulty") == "Medium"]
    hard_probs = [p for p in cc_problems if p.get("difficulty") == "Hard"]

    # 1. CodeChef Easy problems exist
    assert len(easy_probs) >= 4, f"Expected at least 4 Easy CodeChef problems, got {len(easy_probs)}"

    # 2. CodeChef Medium problems exist
    assert len(medium_probs) >= 4, f"Expected at least 4 Medium CodeChef problems, got {len(medium_probs)}"

    # 3. CodeChef Hard problems exist
    assert len(hard_probs) >= 3, f"Expected at least 3 Hard CodeChef problems, got {len(hard_probs)}"

    # 4. Every CodeChef entry schema integrity check
    seen_external_ids = set()
    seen_urls = set()
    problem_codes = set()

    for p in cc_problems:
        ext_id = p.get("external_id")
        url = p.get("url", "")
        title = p.get("title")
        diff = p.get("difficulty")
        skills = p.get("skills")

        assert ext_id, "CodeChef entry missing external_id"
        assert ext_id.startswith("cc_"), f"external_id '{ext_id}' should start with 'cc_'"
        assert ext_id not in seen_external_ids, f"Duplicate external_id found: {ext_id}"
        seen_external_ids.add(ext_id)

        assert url.startswith("https://www.codechef.com/problems/"), f"Invalid CodeChef URL: {url}"
        assert url not in seen_urls, f"Duplicate URL found: {url}"
        seen_urls.add(url)

        assert title, f"CodeChef entry {ext_id} missing title"
        assert diff in ["Easy", "Medium", "Hard"], f"Invalid difficulty '{diff}' for {ext_id}"
        assert isinstance(skills, list) and len(skills) > 0, f"Missing skills for {ext_id}"

        code = ext_id.replace("cc_", "").upper()
        assert code not in problem_codes, f"Duplicate problem code found: {code}"
        problem_codes.add(code)

    # 5. Existing FLOW001 remains present
    assert "cc_flow001" in seen_external_ids, "Existing FLOW001 problem missing!"

    # 6. Existing ATM remains present
    assert "cc_atm" in seen_external_ids, "Existing ATM problem missing!"

    # 7. Difficulty distribution check
    assert len(easy_probs) > 0 and len(medium_probs) > 0 and len(hard_probs) > 0, \
        "Difficulty distribution must have Easy, Medium, and Hard entries"

    # 8. No duplicate CodeChef problem codes check
    assert len(problem_codes) == len(cc_problems), "Duplicate problem codes detected"
