"""Unit and Integration tests for Safe Subprocess Executor, Code Lab Diagnostics, and Submission Pipeline."""

import pytest
from app.services.code_lab.safe_executor import SafeCodeExecutor
from app.services.code_lab.code_lab_service import CodeLabService


def test_safe_code_executor_success():
    executor = SafeCodeExecutor()
    code = "def add(a, b):\n    return a + b\n"
    test_cases = [{"input": "", "function_call": "add(2, 3)", "expected": "5"}]
    res = executor.execute_python_code(code, test_cases, timeout_seconds=2.0)
    assert res["status"] == "passed"
    assert res["passed_count"] == 1


def test_safe_code_executor_timeout():
    executor = SafeCodeExecutor()
    code = "import time\ntime.sleep(5)\n"
    test_cases = [{"input": "", "function_call": "1", "expected": "1"}]
    res = executor.execute_python_code(code, test_cases, timeout_seconds=0.5)
    assert res["status"] == "timeout"


def test_code_lab_service_flow(db_session):
    service = CodeLabService()
    valid_code = """
class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right

def inorder_traversal(root):
    if not root:
        return []
    return inorder_traversal(root.left) + [root.val] + inorder_traversal(root.right)
"""
    analyze_res = service.analyze_code(valid_code, "Python", "problem-tree-inorder")
    assert analyze_res["valid_syntax"] is True
    assert "suggested_code" in analyze_res

    sub_res = service.submit_code("test_user_id", "problem-tree-inorder", valid_code, "Python", db_session)
    assert sub_res["is_passed"] is True
    assert sub_res["telemetry_logged"] is True
