"""Unit and Integration tests for Code Intelligence & Python AST Analysis."""

import pytest
from app.services.analysis.language_detector import detect_language
from app.services.analysis.ast_analyzer import analyze_python_source
from app.services.analysis.code_analyzer import CodeAnalyzerService


def test_language_detector():
    assert detect_language("app/main.py") == "Python"
    assert detect_language("components/Navbar.tsx") == "TypeScript"
    assert detect_language("main.go") == "Go"
    assert detect_language("lib/utils.js") == "JavaScript"
    assert detect_language("UNKNOWN_FILE") == "Plain Text"


def test_python_ast_analysis_basic():
    code = """
def calculate_factorial(n: int) -> int:
    if n <= 1:
        return 1
    return n * calculate_factorial(n - 1)

class MathUtility:
    def __init__(self):
        self.items = [1, 2, 3]
        self.mapping = {"a": 100}
"""
    result = analyze_python_source(code)

    assert result["valid_syntax"] is True
    assert result["function_count"] == 2  # calculate_factorial and __init__
    assert result["class_count"] == 1      # MathUtility
    assert result["has_recursion"] is True
    assert "Recursion" in result["detected_concepts"]
    assert "Functions" in result["detected_concepts"]
    assert "Object-Oriented Programming" in result["detected_concepts"]
    assert "Lists" in result["data_structures"]
    assert "Dictionaries" in result["data_structures"]


def test_python_ast_analysis_comprehensions_and_try_except():
    code = """
import sys

def process_numbers(numbers):
    try:
        squares = [x ** 2 for x in numbers if x > 0]
        cubes = {x: x ** 3 for x in numbers}
        return squares, cubes
    except Exception as e:
        print("Error:", e)
        return [], {}
"""
    result = analyze_python_source(code)

    assert result["valid_syntax"] is True
    assert result["function_count"] == 1
    assert "List Comprehensions" in result["detected_concepts"]
    assert "Dict Comprehensions" in result["detected_concepts"]
    assert "Error Handling" in result["detected_concepts"]
    assert "sys" in result["imports"]


def test_code_analyzer_service():
    service = CodeAnalyzerService()
    file_path = "services/tree.py"
    code = """
def dfs(node):
    if not node:
        return []
    return [node.val] + dfs(node.left) + dfs(node.right)
"""
    result = service.analyze(file_path, code)

    assert result["language"] == "Python"
    assert result["has_recursion"] is True
    assert "Tree/Graph Traversal" in result["detected_concepts"]
    assert "Recursion" in result["detected_concepts"]
