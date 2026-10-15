"""Concrete Static Analyzers for multi-language AST extraction."""

import ast
import re
from typing import Any

def parse_python(code: str) -> dict[str, Any]:
    """Parse Python source code using built-in ast module."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return {"error": "Invalid Python syntax", "classes": [], "functions": []}

    classes = []
    functions = []
    
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
            classes.append({"name": node.name, "methods": methods})
        elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            functions.append(node.name)
            
    # Quick control flow sweep
    loops = sum(1 for _ in ast.walk(tree) if isinstance(_, (ast.For, ast.While, ast.AsyncFor)))
    conditionals = sum(1 for _ in ast.walk(tree) if isinstance(_, (ast.If, ast.IfExp)))
    
    return {
        "classes": classes,
        "functions": functions,
        "loops_count": loops,
        "conditionals_count": conditionals,
    }

def parse_java(code: str) -> dict[str, Any]:
    """Parse Java source code using javalang."""
    try:
        import javalang
    except ImportError:
        return {"error": "javalang not installed"}

    try:
        # Wrap in class if it's just a method snippet
        if "class " not in code and "interface " not in code:
            wrapped = f"public class Wrapper {{\n{code}\n}}"
            tree = javalang.parse.parse(wrapped)
        else:
            tree = javalang.parse.parse(code)
    except Exception as e:
        return {"error": f"Invalid Java syntax: {str(e)}", "classes": [], "methods": []}

    classes = []
    methods = []
    
    for path, node in tree.filter(javalang.tree.ClassDeclaration):
        class_methods = [m.name for m in node.methods]
        classes.append({"name": node.name, "methods": class_methods})
        methods.extend(class_methods)
        
    loops = sum(1 for _, _ in tree.filter((javalang.tree.ForStatement, javalang.tree.WhileStatement, javalang.tree.DoStatement)))
    conditionals = sum(1 for _, _ in tree.filter((javalang.tree.IfStatement, javalang.tree.SwitchStatement)))
    
    return {
        "classes": classes,
        "methods": methods,
        "loops_count": loops,
        "conditionals_count": conditionals,
    }

def parse_c(code: str) -> dict[str, Any]:
    """Parse C source code using pycparser with fallback regex."""
    # Strip includes because pycparser fails without fake libc headers
    code_no_includes = "\n".join([line for line in code.splitlines() if not line.strip().startswith("#")])
    
    try:
        from pycparser import c_parser, c_ast
        parser = c_parser.CParser()
        tree = parser.parse(code_no_includes, filename='<none>')
        
        functions = []
        for node in tree.ext:
            if isinstance(node, c_ast.FuncDef):
                functions.append(node.decl.name)
                
        # Basic counting via visitor
        class CounterVisitor(c_ast.NodeVisitor):
            def __init__(self):
                self.loops = 0
                self.conditionals = 0
                
            def visit_For(self, node):
                self.loops += 1
                self.generic_visit(node)
                
            def visit_While(self, node):
                self.loops += 1
                self.generic_visit(node)
                
            def visit_DoWhile(self, node):
                self.loops += 1
                self.generic_visit(node)
                
            def visit_If(self, node):
                self.conditionals += 1
                self.generic_visit(node)

        visitor = CounterVisitor()
        visitor.visit(tree)
        
        return {
            "functions": functions,
            "loops_count": visitor.loops,
            "conditionals_count": visitor.conditionals,
        }
    except Exception as e:
        # Fallback to simple regex if parser fails (e.g., weird macros)
        funcs = re.findall(r'^\s*(?:[\w\s\*]+)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)\s*\{', code, re.MULTILINE)
        loops = len(re.findall(r'\b(for|while)\s*\(', code))
        conditionals = len(re.findall(r'\b(if|switch)\s*\(', code))
        return {
            "error": "Used regex fallback",
            "functions": funcs,
            "loops_count": loops,
            "conditionals_count": conditionals,
        }

def get_structural_schema(language: str, code: str) -> dict[str, Any]:
    """Return AST-derived structural schema based on language."""
    lang = language.lower()
    if lang == "python":
        return parse_python(code)
    elif lang == "java":
        return parse_java(code)
    elif lang in ["c", "cpp", "c++"]:
        return parse_c(code)
    else:
        return {"error": f"No concrete parser available for {language}"}
