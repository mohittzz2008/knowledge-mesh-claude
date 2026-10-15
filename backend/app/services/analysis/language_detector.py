"""Language Detection Utility based on file extension and path heuristics."""

from typing import Optional

EXTENSION_MAP = {
    ".py": "Python",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".go": "Go",
    ".rs": "Rust",
    ".c": "C",
    ".cpp": "C++",
    ".h": "C/C++",
    ".hpp": "C++",
    ".java": "Java",
    ".kt": "Kotlin",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".swift": "Swift",
    ".sql": "SQL",
    ".sh": "Shell",
    ".json": "JSON",
    ".md": "Markdown",
}


def detect_language(file_path: str, default_language: str = "Plain Text") -> str:
    """Detect programming language from file path extension."""
    if not file_path:
        return default_language

    path_lower = file_path.lower()
    for ext, lang in EXTENSION_MAP.items():
        if path_lower.endswith(ext):
            return lang

    return default_language
