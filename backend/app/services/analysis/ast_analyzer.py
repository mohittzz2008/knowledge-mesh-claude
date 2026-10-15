"""Python AST and Static Code Analyzer Service."""

import ast
from typing import Any, Optional


class PythonASTVisitor(ast.NodeVisitor):
    """AST NodeVisitor extracting static analysis metrics and concepts from Python source."""

    def __init__(self):
        self.function_count = 0
        self.async_function_count = 0
        self.class_count = 0
        self.cyclomatic_complexity = 1
        self.has_recursion = False
        
        self.detected_concepts: set[str] = set()
        self.data_structures: set[str] = set()
        self.imports: set[str] = set()
        self.function_names: list[str] = []
        self.class_names: list[str] = []

        self._current_function: Optional[str] = None

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.function_count += 1
        self.function_names.append(node.name)
        self.detected_concepts.add("Functions")

        old_fn = self._current_function
        self._current_function = node.name

        # Recursion check & tree traversal indicator inside function
        if any(term in node.name.lower() for term in ["dfs", "bfs", "traverse", "inorder", "preorder", "postorder"]):
            self.detected_concepts.add("Tree/Graph Traversal")

        self.generic_visit(node)
        self._current_function = old_fn

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self.function_count += 1
        self.async_function_count += 1
        self.function_names.append(node.name)
        self.detected_concepts.add("Functions")
        self.detected_concepts.add("Async Programming")

        old_fn = self._current_function
        self._current_function = node.name
        self.generic_visit(node)
        self._current_function = old_fn

    def visit_ClassDef(self, node: ast.ClassDef):
        self.class_count += 1
        self.class_names.append(node.name)
        self.detected_concepts.add("Object-Oriented Programming")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        # Recursion detection (direct call to self or function name)
        if self._current_function:
            callee_name = None
            if isinstance(node.func, ast.Name):
                callee_name = node.func.id
            elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                if node.func.value.id == "self":
                    callee_name = node.func.attr

            if callee_name and callee_name == self._current_function:
                self.has_recursion = True
                self.detected_concepts.add("Recursion")

        # Built-in data structure constructors
        if isinstance(node.func, ast.Name):
            name = node.func.id
            if name == "list":
                self.data_structures.add("Lists")
            elif name == "dict":
                self.data_structures.add("Dictionaries")
            elif name == "set":
                self.data_structures.add("Sets")
            elif name == "tuple":
                self.data_structures.add("Tuples")
            elif name == "deque":
                self.data_structures.add("Queues/Deques")

        self.generic_visit(node)

    def visit_List(self, node: ast.List):
        self.data_structures.add("Lists")
        self.generic_visit(node)

    def visit_Dict(self, node: ast.Dict):
        self.data_structures.add("Dictionaries")
        self.generic_visit(node)

    def visit_Set(self, node: ast.Set):
        self.data_structures.add("Sets")
        self.generic_visit(node)

    def visit_Tuple(self, node: ast.Tuple):
        self.data_structures.add("Tuples")
        self.generic_visit(node)

    def visit_ListComp(self, node: ast.ListComp):
        self.detected_concepts.add("List Comprehensions")
        self.data_structures.add("Lists")
        self.generic_visit(node)

    def visit_DictComp(self, node: ast.DictComp):
        self.detected_concepts.add("Dict Comprehensions")
        self.data_structures.add("Dictionaries")
        self.generic_visit(node)

    def visit_SetComp(self, node: ast.SetComp):
        self.detected_concepts.add("Set Comprehensions")
        self.data_structures.add("Sets")
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try):
        self.detected_concepts.add("Error Handling")
        self.cyclomatic_complexity += 1
        self.generic_visit(node)

    def visit_If(self, node: ast.If):
        self.cyclomatic_complexity += 1
        self.generic_visit(node)

    def visit_For(self, node: ast.For):
        self.cyclomatic_complexity += 1
        self.detected_concepts.add("Iteration")
        self.generic_visit(node)

    def visit_While(self, node: ast.While):
        self.cyclomatic_complexity += 1
        self.detected_concepts.add("Iteration")
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp):
        self.cyclomatic_complexity += len(node.values) - 1
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imports.add(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module:
            self.imports.add(node.module)
        self.generic_visit(node)


def analyze_python_source(code_content: str) -> dict[str, Any]:
    """Parse Python source code using AST and return comprehensive static analysis metrics."""
    lines = code_content.splitlines()
    loc = len([l for l in lines if l.strip() and not l.strip().startswith("#")])

    try:
        tree = ast.parse(code_content)
        visitor = PythonASTVisitor()
        visitor.visit(tree)

        concepts = sorted(list(visitor.detected_concepts))
        data_structs = sorted(list(visitor.data_structures))

        if visitor.cyclomatic_complexity > 10:
            concepts.append("High Cyclomatic Complexity")

        return {
            "valid_syntax": True,
            "lines_of_code": loc,
            "function_count": visitor.function_count,
            "class_count": visitor.class_count,
            "cyclomatic_complexity": visitor.cyclomatic_complexity,
            "has_recursion": visitor.has_recursion,
            "detected_concepts": concepts,
            "data_structures": data_structs,
            "imports": sorted(list(visitor.imports)),
            "function_names": visitor.function_names,
            "class_names": visitor.class_names,
            "error_detail": None,
        }
    except SyntaxError as err:
        return {
            "valid_syntax": False,
            "lines_of_code": loc,
            "function_count": 0,
            "class_count": 0,
            "cyclomatic_complexity": 1,
            "has_recursion": False,
            "detected_concepts": ["Syntax Error"],
            "data_structures": [],
            "imports": [],
            "function_names": [],
            "class_names": [],
            "error_detail": f"SyntaxError at line {err.lineno}: {err.msg}",
        }
