"""Pydantic schemas for Code Lab APIs."""

from typing import Optional, Any
from pydantic import BaseModel


class TestCaseResultSchema(BaseModel):
    test_case: int
    passed: bool
    actual: str
    expected: str
    error: Optional[str] = None


class CodeRunRequest(BaseModel):
    code: str
    language: str = "Python"
    problem_id: str = "problem-tree-inorder"


class CodeRunResponse(BaseModel):
    status: str  # 'passed' | 'failed' | 'error' | 'timeout'
    stdout: str
    stderr: str
    execution_time_ms: float
    passed_count: int
    total_tests: int
    test_results: list[TestCaseResultSchema] = []
    error_message: Optional[str] = None


class CodeAnalyzeRequest(BaseModel):
    code: str
    language: str = "Python"
    problem_id: str = "problem-tree-inorder"


class CodeAnalyzeResponse(BaseModel):
    valid_syntax: bool
    ast_metrics: dict[str, Any]
    diagnostic_report: str
    original_code: str
    suggested_code: str
    explanation: str


class CodeSubmitRequest(BaseModel):
    code: str
    language: str = "Python"
    problem_id: str = "problem-tree-inorder"


class CodeSubmitResponse(BaseModel):
    attempt_id: str
    status: str
    is_passed: bool
    execution_time_ms: float
    passed_count: int
    total_tests: int
    diagnostic_report: str
    telemetry_logged: bool
    evidence_id: str
    message: str


class CodeHintRequest(BaseModel):
    problem_id: str = "problem-tree-inorder"
    hint_level: int = 1


class CodeHintResponse(BaseModel):
    problem_id: str
    hint_level: int
    total_hints: int
    hint: str
