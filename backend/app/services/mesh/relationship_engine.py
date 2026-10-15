"""Skill Relationship Engine and Seeder."""

from typing import Any
from sqlalchemy.orm import Session
from app.models.skill import Skill, SkillRelationship

# Controlled, verified skill taxonomy and relationship definitions
CONTROLLED_SKILLS = [
    {"name": "Functions", "slug": "functions", "category": "core", "description": "Function definitions, parameter passing, return values"},
    {"name": "Iteration", "slug": "iteration", "category": "core", "description": "For loops, while loops, and iterator patterns"},
    {"name": "Object-Oriented Programming", "slug": "object-oriented-programming", "category": "core", "description": "Classes, objects, attributes, and methods"},
    {"name": "Error Handling", "slug": "error-handling", "category": "core", "description": "Try/except exception handling and defensive programming"},
    {"name": "Lists", "slug": "lists", "category": "core", "description": "Dynamic arrays, list operations, and list comprehensions"},
    {"name": "Dictionaries", "slug": "dictionaries", "category": "core", "description": "Key-value hash maps, dict operations, and dict comprehensions"},
    {"name": "Sets", "slug": "sets", "category": "core", "description": "Unique element collections and set operations"},
    {"name": "Arrays", "slug": "arrays", "category": "core", "description": "Contiguous memory sequence access and array manipulation"},
    {"name": "Hashing", "slug": "hashing", "category": "core", "description": "Hash functions, hash tables, and O(1) lookup strategies"},
    {"name": "Problem Solving", "slug": "problem-solving", "category": "core", "description": "Algorithmic problem solving, challenge analysis, and test case reasoning"},
    {"name": "Python", "slug": "python", "category": "languages", "description": "Python language proficiency, syntax, and standard library idioms"},
    {"name": "C", "slug": "c", "category": "languages", "description": "C programming language, pointers, and memory management"},
    {"name": "Recursion", "slug": "recursion", "category": "advanced", "description": "Self-referencing function calls, base cases, and call stacks"},
    {"name": "Tree Traversal", "slug": "tree-traversal", "category": "advanced", "description": "Inorder, preorder, postorder, and tree search algorithms"},
    {"name": "DFS", "slug": "dfs", "category": "advanced", "description": "Depth-First Search graph and tree exploration"},
    {"name": "Graph Algorithms", "slug": "graph-algorithms", "category": "advanced", "description": "Adjacency lists, shortest path, and topological sorting"},
    {"name": "Async Programming", "slug": "async-programming", "category": "advanced", "description": "Asynchronous event loops, tasks, and coroutines"},
]

CONTROLLED_RELATIONSHIPS = [
    ("functions", "recursion", "prerequisite"),
    ("recursion", "tree-traversal", "prerequisite"),
    ("tree-traversal", "dfs", "prerequisite"),
    ("dfs", "graph-algorithms", "related_to"),
    ("lists", "arrays", "related_to"),
    ("arrays", "hashing", "related_to"),
    ("dictionaries", "hashing", "prerequisite"),
    ("iteration", "tree-traversal", "related_to"),
    ("functions", "async-programming", "prerequisite"),
    ("problem-solving", "recursion", "related_to"),
    ("python", "functions", "related_to"),
    ("c", "functions", "related_to"),
]


def seed_controlled_skills_and_relationships(db: Session) -> dict[str, Skill]:
    """Seed or return controlled skill definitions and relationships in PostgreSQL."""
    skill_map: dict[str, Skill] = {}

    for s_def in CONTROLLED_SKILLS:
        skill = db.query(Skill).filter(Skill.slug == s_def["slug"]).first()
        if not skill:
            skill = Skill(
                name=s_def["name"],
                slug=s_def["slug"],
                category=s_def["category"],
                description=s_def["description"],
            )
            db.add(skill)
            db.commit()
            db.refresh(skill)
        skill_map[s_def["slug"]] = skill

    for parent_slug, child_slug, rel_type in CONTROLLED_RELATIONSHIPS:
        p_skill = skill_map.get(parent_slug)
        c_skill = skill_map.get(child_slug)
        if p_skill and c_skill:
            existing_rel = (
                db.query(SkillRelationship)
                .filter(
                    SkillRelationship.parent_skill_id == p_skill.id,
                    SkillRelationship.child_skill_id == c_skill.id,
                )
                .first()
            )
            if not existing_rel:
                rel = SkillRelationship(
                    parent_skill_id=p_skill.id,
                    child_skill_id=c_skill.id,
                    relationship_type=rel_type,
                )
                db.add(rel)
    
    db.commit()
    return skill_map
