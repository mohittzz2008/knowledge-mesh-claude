"""Code Lab Service Orchestrator."""

from datetime import datetime, timezone
from typing import Any, Optional
from sqlalchemy.orm import Session

from app.models.problem import Problem, CodeAttempt
from app.models.evidence import Evidence
from app.models.code_artifact import CodeArtifact, CodeAnalysis
from app.services.code_lab.safe_executor import SafeCodeExecutor
from app.services.analysis.ast_analyzer import analyze_python_source
from app.services.mesh.concept_extractor import ConceptExtractorService

CODE_LAB_PROBLEMS = [
    {
        "id": "problem-tree-inorder",
        "title": "Binary Tree Inorder Traversal",
        "slug": "tree-traversal",
        "difficulty": "Easy",
        "target_skill": "Tree Traversal",
        "learning_objective": "Master recursive tree traversal and call stack base condition termination.",
        "description": "Given the root of a binary tree, return the inorder traversal of its nodes' values.\n\nInorder Traversal: Left Subtree -> Root Node -> Right Subtree.",
        "initial_code": """class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right

def inorder_traversal(root):
    # Implement recursive inorder tree traversal
    if not root:
        return []
    return inorder_traversal(root.left) + [root.val] + inorder_traversal(root.right)
""",
        "suggested_code": """class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right

def inorder_traversal(root):
    \"\"\"Optimal recursive inorder tree traversal with helper collector.\"\"\"
    result = []
    
    def traverse(node):
        if not node:
            return
        traverse(node.left)
        result.append(node.val)
        traverse(node.right)
        
    traverse(root)
    return result
""",
        "test_cases": [
            {
                "input": "n3 = TreeNode(3)\nn2 = TreeNode(2, n3, None)\nroot = TreeNode(1, None, n2)",
                "function_call": "inorder_traversal(root)",
                "expected": "[1, 3, 2]",
            },
            {
                "input": "root = None",
                "function_call": "inorder_traversal(root)",
                "expected": "[]",
            },
            {
                "input": "root = TreeNode(1)",
                "function_call": "inorder_traversal(root)",
                "expected": "[1]",
            },
        ],
        "hints": [
            "Hint 1: Check your base condition when the current node is None.",
            "Hint 2: Recursive order must be: traverse left child first, process root value, then traverse right child.",
            "Hint 3: Use an auxiliary inner helper function `traverse(node)` to avoid repeated list concatenation memory overhead.",
        ],
    },
    {
        "id": "problem-recursion-factorial",
        "title": "Recursive Factorial Calculation",
        "slug": "recursion",
        "difficulty": "Easy",
        "target_skill": "Recursion",
        "learning_objective": "Implement basic single-path recursion with base case termination.",
        "description": "Write a function `factorial(n)` that returns the factorial of integer `n` using recursion.\n\nFactorial of n = n * (n - 1) * ... * 1. Base case: factorial(0) = 1.",
        "initial_code": """def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)
""",
        "suggested_code": """def factorial(n):
    \"\"\"Calculates factorial recursively with input validation.\"\"\"
    if n < 0:
        raise ValueError("Factorial is undefined for negative integers")
    if n <= 1:
        return 1
    return n * factorial(n - 1)
""",
        "test_cases": [
            {
                "input": "n = 5",
                "function_call": "factorial(5)",
                "expected": "120",
            },
            {
                "input": "n = 0",
                "function_call": "factorial(0)",
                "expected": "1",
            },
        ],
        "hints": [
            "Hint 1: Identify the base case when n <= 1.",
            "Hint 2: Ensure the recursive call decrements n by 1 (`factorial(n - 1)`).",
        ],
    },
]


class CodeLabService:
    """Service handling Code Lab execution, AST diagnostics, hints, and evidence pipeline integration."""

    def get_problem_detail(self, problem_id: str) -> Optional[dict[str, Any]]:
        for p in CODE_LAB_PROBLEMS:
            if p["id"] == problem_id or p["slug"] == problem_id:
                return p
        return CODE_LAB_PROBLEMS[0]

    def run_code(self, code: str, language: str, problem_id: str) -> dict[str, Any]:
        p = self.get_problem_detail(problem_id)
        test_cases = p["test_cases"] if p else []

        executor = SafeCodeExecutor()
        exec_res = executor.execute_python_code(code, test_cases, timeout_seconds=3.0)
        return exec_res

    def analyze_code(self, code: str, language: str, problem_id: str) -> dict[str, Any]:
        p = self.get_problem_detail(problem_id)

        from app.services.analysis.code_analyzer import CodeAnalyzerService
        ext_map = {"Python": ".py", "Java": ".java", "C": ".c", "C++": ".cpp"}
        analyzer = CodeAnalyzerService()
        analysis = analyzer.analyze(f"test{ext_map.get(language, '.txt')}", code)
        
        ast_metrics = analysis["analysis_summary"]
        ast_metrics.update({
            "lines_of_code": analysis["lines_of_code"],
            "function_count": analysis["function_count"],
            "class_count": analysis["class_count"],
            "cyclomatic_complexity": analysis["cyclomatic_complexity"],
            "has_recursion": analysis["has_recursion"],
            "detected_concepts": analysis["detected_concepts"],
            "data_structures": analysis["data_structures"],
        })

        has_rec = ast_metrics.get("has_recursion", False)
        concepts = ast_metrics.get("detected_concepts", [])
        complexity = ast_metrics.get("cyclomatic_complexity", 1)

        diagnostic_report = (
            f"AI DIAGNOSTIC ANALYSIS:\n"
            f"• Syntax Validity: {'Valid' if ast_metrics.get('valid_syntax') else 'Syntax Error'}\n"
            f"• Recursion Detected: {'Yes (Self-referencing call frame)' if has_rec else 'No'}\n"
            f"• Cyclomatic Complexity: {complexity}\n"
            f"• Detected Concepts: {', '.join(concepts) if concepts else 'Basic Logic'}\n"
            f"• Functions Count: {ast_metrics.get('function_count', 0)}\n\n"
            f"REASONING & TRADEOFFS:\n"
            f"Your approach demonstrates clean recursion. Standard call stack space complexity is O(H) where H is recursion depth."
        )

        return {
            "valid_syntax": ast_metrics.get("valid_syntax", True),
            "ast_metrics": ast_metrics,
            "diagnostic_report": diagnostic_report,
            "original_code": code,
            "suggested_code": p["suggested_code"] if p else code,
            "explanation": (
                f"Suggested Approach Optimization: Avoids repeated list concatenation in recursion by using an accumulator pattern or helper traversal function."
            ),
        }

    def submit_code(
        self, user_id: str, problem_id: str, code: str, language: str, db: Session
    ) -> dict[str, Any]:
        p = self.get_problem_detail(problem_id)
        exec_res = self.run_code(code, language, problem_id)
        analysis_res = self.analyze_code(code, language, problem_id)

        is_passed = exec_res["status"] == "passed"

        # 1. Record Problem reference if not existing
        problem_obj = db.query(Problem).filter(Problem.external_id == p["id"]).first()
        if not problem_obj:
            problem_obj = Problem(
                platform="CodeLab",
                external_id=p["id"],
                title=p["title"],
                difficulty=p["difficulty"],
                topics={"skills": [p["slug"]]},
                language=language,
                description=p["description"],
                source="Knowledge Mesh Code Lab",
            )
            db.add(problem_obj)
            db.commit()
            db.refresh(problem_obj)

        # 2. Record CodeAttempt in PostgreSQL
        attempt = CodeAttempt(
            user_id=user_id,
            problem_id=problem_obj.id,
            status="completed" if is_passed else "failed",
            source_platform="CodeLab",
            created_at=datetime.now(timezone.utc),
        )
        db.add(attempt)

        # Fetch or create platform connection for user
        from app.models.platform import PlatformConnection
        conn = db.query(PlatformConnection).filter(
            PlatformConnection.user_id == user_id,
            PlatformConnection.platform == "GitHub"
        ).first()
        if not conn:
            conn = PlatformConnection(
                user_id=user_id,
                platform="GitHub",
                auth_type="username_public",
                username="demo_user",
                connected=True,
            )
            db.add(conn)
            db.commit()
            db.refresh(conn)

        # 3. Create CodeArtifact & CodeAnalysis in PostgreSQL
        artifact = CodeArtifact(
            user_id=user_id,
            platform_connection_id=conn.id,
            platform="CodeLab",
            repository="knowledge-mesh/code-lab",
            file_path=f"code-lab/{p['slug']}.py",
            language=language,
            code_content=code,
            size_bytes=len(code.encode('utf-8')),
            created_at=datetime.now(timezone.utc),
        )
        db.add(artifact)
        db.commit()
        db.refresh(artifact)

        ast_m = analysis_res["ast_metrics"]
        code_analysis = CodeAnalysis(
            code_artifact_id=artifact.id,
            language=language,
            lines_of_code=ast_m.get("lines_of_code", 10),
            function_count=ast_m.get("function_count", 1),
            class_count=ast_m.get("class_count", 0),
            cyclomatic_complexity=ast_m.get("cyclomatic_complexity", 1),
            has_recursion=ast_m.get("has_recursion", False),
            detected_concepts=ast_m.get("detected_concepts", []),
            data_structures=ast_m.get("data_structures", []),
            analysis_summary=ast_m,
            created_at=datetime.now(timezone.utc),
        )
        db.add(code_analysis)

        # 4. Generate normalized Evidence record in PostgreSQL
        evidence = Evidence(
            user_id=user_id,
            platform_connection_id=conn.id,
            title=f"Code Lab Solution: {p['title']}",
            evidence_type="code_lab_attempt",
            raw_payload={"code_artifact_id": artifact.id, "passed": is_passed},
            normalized_payload={
                "skills": ast_m.get("detected_concepts", [p["target_skill"]]),
                "passed": is_passed,
                "problem": p["title"],
            },
            created_at=datetime.now(timezone.utc),
        )
        db.add(evidence)
        db.commit()

        # 5. Re-evaluate Knowledge Mesh Assessments
        extractor = ConceptExtractorService()
        extractor.extract_and_assess_user_skills(user_id, db)

        return {
            "attempt_id": attempt.id,
            "status": "ACCEPTED" if is_passed else "FAILED",
            "is_passed": is_passed,
            "execution_time_ms": exec_res["execution_time_ms"],
            "passed_count": exec_res["passed_count"],
            "total_tests": exec_res["total_tests"],
            "diagnostic_report": analysis_res["diagnostic_report"],
            "telemetry_logged": True,
            "evidence_id": evidence.id,
            "message": f"Submission logged to Knowledge Mesh. Skill telemetry updated for '{p['target_skill']}' in PostgreSQL.",
        }

    def get_hint(self, problem_id: str, hint_level: int = 1) -> dict[str, Any]:
        p = self.get_problem_detail(problem_id)
        hints = p.get("hints", []) if p else []

        idx = min(max(hint_level - 1, 0), len(hints) - 1) if hints else 0
        hint_text = hints[idx] if hints else "Review base condition and recursive function parameters."

        return {
            "problem_id": problem_id,
            "hint_level": idx + 1,
            "total_hints": len(hints),
            "hint": hint_text,
        }
