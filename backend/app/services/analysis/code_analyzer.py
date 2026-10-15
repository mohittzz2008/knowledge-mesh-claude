"""High-Level Code Analyzer Orchestrator."""

from typing import Any
import re
from app.services.analysis.language_detector import detect_language
from app.services.analysis.ast_analyzer import analyze_python_source


class CodeAnalyzerService:
    """Orchestrates language detection, AST parsing, and evidence payload generation."""

    def analyze(self, file_path: str, code_content: str) -> dict[str, Any]:
        """Analyze source code content and return standardized static code metrics."""
        language = detect_language(file_path)

        if language == "Python":
            analysis_data = analyze_python_source(code_content)
        else:
            # Fallback structural analyzer for non-Python languages
            lines = code_content.splitlines()
            loc = len([l for l in lines if l.strip()])
            
            # Simple heuristic regex for C/C++/Java classes
            extracted_classes = re.findall(r'(?:class|struct|interface)\s+([A-Za-z0-9_]+)', code_content)
            
            # Heuristic for functions: Words preceding '(' ignoring common control-flow keywords
            extracted_funcs = []
            for match in re.finditer(r'\b([A-Za-z0-9_]+)\s*\(', code_content):
                name = match.group(1)
                if name not in {"if", "for", "while", "switch", "catch", "return", "new", "sizeof", "super", "this"}:
                    extracted_funcs.append(name)
            extracted_funcs = list(set(extracted_funcs))
            
            analysis_data = {
                "valid_syntax": True,
                "lines_of_code": loc,
                "function_count": len(extracted_funcs) if extracted_funcs else code_content.count("function ") + code_content.count("fn "),
                "class_count": len(extracted_classes) if extracted_classes else code_content.count("class "),
                "cyclomatic_complexity": 1 + code_content.count("if ") + code_content.count("for ") + code_content.count("while "),
                "has_recursion": False,
                "detected_concepts": ["Structural Analysis"],
                "data_structures": [],
                "imports": [],
                "function_names": extracted_funcs,
                "class_names": extracted_classes,
                "error_detail": None,
            }

        return {
            "language": language,
            "file_path": file_path,
            "lines_of_code": analysis_data["lines_of_code"],
            "function_count": analysis_data["function_count"],
            "class_count": analysis_data["class_count"],
            "cyclomatic_complexity": analysis_data["cyclomatic_complexity"],
            "has_recursion": analysis_data["has_recursion"],
            "detected_concepts": analysis_data["detected_concepts"],
            "data_structures": analysis_data["data_structures"],
            "analysis_summary": {
                "imports": analysis_data["imports"],
                "function_names": analysis_data["function_names"],
                "class_names": analysis_data["class_names"],
                "valid_syntax": analysis_data["valid_syntax"],
                "error_detail": analysis_data.get("error_detail"),
            },
        }

    def normalize_to_evidence(self, artifact_data: dict[str, Any], analysis_result: dict[str, Any]) -> dict[str, Any]:
        """Convert a CodeArtifact + CodeAnalysis into standardized Knowledge Mesh Evidence telemetry."""
        skills = list(set(
            [analysis_result["language"]]
            + analysis_result["detected_concepts"]
            + analysis_result["data_structures"]
        ))

        return {
            "platform": artifact_data.get("platform", "GitHub"),
            "external_id": artifact_data.get("commit_sha") or artifact_data.get("id"),
            "title": f"Code Analysis: {artifact_data.get('repository')}/{artifact_data.get('file_path')}",
            "evidence_type": "code_analysis",
            "source_url": artifact_data.get("source_url"),
            "occurred_at": artifact_data.get("created_at"),
            "raw_payload": {
                "artifact": artifact_data,
                "analysis": analysis_result,
            },
            "normalized_payload": {
                "repository": artifact_data.get("repository"),
                "file_path": artifact_data.get("file_path"),
                "language": analysis_result["language"],
                "lines_of_code": analysis_result["lines_of_code"],
                "function_count": analysis_result["function_count"],
                "class_count": analysis_result["class_count"],
                "cyclomatic_complexity": analysis_result["cyclomatic_complexity"],
                "has_recursion": analysis_result["has_recursion"],
                "detected_concepts": analysis_result["detected_concepts"],
                "data_structures": analysis_result["data_structures"],
                "skills": skills,
            },
        }
