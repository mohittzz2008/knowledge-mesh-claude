"""Problem Matcher & Practice Ranking Service."""

from typing import Any, Optional
from sqlalchemy.orm import Session

from app.models.problem import Problem, ProblemRecommendation, CodeAttempt
from app.models.evidence import Evidence
from app.services.platform import external_platform_names


CONTROLLED_PRACTICE_PROBLEMS = [

    {
        "platform": "GitHub",
        "external_id": "gh_rec_01",
        "title": "Recursive Function Patterns & Call Stack Verification",
        "url": "https://github.com/python/cpython/blob/main/Lib/ast.py",
        "difficulty": "Easy",
        "topics": ["Recursion", "Functions"],
        "language": "Python",
        "description": "Analyze recursive function call stacks and base condition termination.",
        "source": "GitHub Official Public Repository",
        "skills": ["recursion", "functions"],
    },
    {
        "platform": "GitHub",
        "external_id": "gh_rec_02",
        "title": "Recursive Binary Tree DFS Traversal",
        "url": "https://github.com/fastapi/fastapi/blob/main/fastapi/applications.py",
        "difficulty": "Easy",
        "topics": ["Tree Traversal", "Recursion", "DFS"],
        "language": "Python",
        "description": "Implement inorder and preorder tree traversal using recursion.",
        "source": "GitHub Official Public Repository",
        "skills": ["tree-traversal", "recursion", "dfs"],
    },
    {
        "platform": "LeetCode",
        "external_id": "lc_104",
        "title": "Maximum Depth of Binary Tree (Reference)",
        "url": "https://leetcode.com/problems/maximum-depth-of-binary-tree/",
        "difficulty": "Easy",
        "topics": ["Tree", "Depth-First Search", "Binary Tree"],
        "language": "Python",
        "description": "Permitted platform problem reference for binary tree depth calculation.",
        "source": "LeetCode Platform Reference",
        "skills": ["tree-traversal", "dfs"],
    },
    {
        "platform": "HackerRank",
        "external_id": "hr_tree_preorder",
        "title": "Tree: Preorder Traversal (Reference)",
        "url": "https://www.hackerrank.com/challenges/tree-preorder-traversal",
        "difficulty": "Easy",
        "topics": ["Trees", "Data Structures"],
        "language": "Python",
        "description": "Permitted platform problem reference for tree preorder traversal.",
        "source": "HackerRank Platform Reference",
        "skills": ["tree-traversal"],
    },
    {
        "platform": "HackerRank",
        "external_id": "hr_nested_lists",
        "title": "Nested Lists",
        "url": "https://www.hackerrank.com/challenges/nested-list/problem",
        "difficulty": "Easy",
        "topics": ["Lists", "Python"],
        "language": "Python",
        "description": "Store and query students with second lowest grade using nested lists.",
        "source": "HackerRank Challenge",
        "skills": ["lists", "python"],
    },
    {
        "platform": "HackerRank",
        "external_id": "hr_sets_intro",
        "title": "Introduction to Sets",
        "url": "https://www.hackerrank.com/challenges/py-introduction-to-sets/problem",
        "difficulty": "Easy",
        "topics": ["Sets", "Python"],
        "language": "Python",
        "description": "Calculate average of distinct plant heights using set operations.",
        "source": "HackerRank Challenge",
        "skills": ["sets", "python"],
    },
    {
        "platform": "HackerRank",
        "external_id": "hr_simple_array_sum",
        "title": "Simple Array Sum",
        "url": "https://www.hackerrank.com/challenges/simple-array-sum/problem",
        "difficulty": "Easy",
        "topics": ["Arrays", "Algorithms", "Problem Solving"],
        "language": "C",
        "description": "Compute the sum of an array of integers.",
        "source": "HackerRank Challenge",
        "skills": ["arrays", "problem-solving"],
    },
    {
        "platform": "LeetCode",
        "external_id": "lc_217",
        "title": "Contains Duplicate",
        "url": "https://leetcode.com/problems/contains-duplicate/",
        "difficulty": "Easy",
        "topics": ["Array", "Hash Table", "Sorting"],
        "language": "Python",
        "description": "Determine if any value appears at least twice in an integer array using sets.",
        "source": "LeetCode Challenge",
        "skills": ["arrays", "sets", "hashing"],
    },
    {
        "platform": "LeetCode",
        "external_id": "lc_200",
        "title": "Number of Islands",
        "url": "https://leetcode.com/problems/number-of-islands/",
        "difficulty": "Medium",
        "topics": ["Array", "Depth-First Search", "Breadth-First Search", "Matrix"],
        "language": "Python",
        "description": "Count the number of islands in a 2D binary grid using DFS graph traversal.",
        "source": "LeetCode Challenge",
        "skills": ["graph-algorithms", "dfs"],
    },
    {
        "platform": "Exercism",
        "external_id": "exercism_track_python",
        "title": "Exercism Python Track",
        "url": "https://exercism.org/tracks/python",
        "difficulty": "Adaptive",
        "topics": ["Python", "Language Track"],
        "language": "Python",
        "description": "Practice and master Python via the official Exercism track.",
        "source": "Exercism API (Track Reputation)",
        "skills": ["python"],
    },
    {
        "platform": "Exercism",
        "external_id": "exercism_track_javascript",
        "title": "Exercism JavaScript Track",
        "url": "https://exercism.org/tracks/javascript",
        "difficulty": "Adaptive",
        "topics": ["JavaScript", "Language Track"],
        "language": "JavaScript",
        "description": "Practice and master JavaScript via the official Exercism track.",
        "source": "Exercism API (Track Reputation)",
        "skills": ["javascript"],
    },
    {
        "platform": "Exercism",
        "external_id": "exercism_track_java",
        "title": "Exercism Java Track",
        "url": "https://exercism.org/tracks/java",
        "difficulty": "Adaptive",
        "topics": ["Java", "Language Track"],
        "language": "Java",
        "description": "Practice and master Java via the official Exercism track.",
        "source": "Exercism API (Track Reputation)",
        "skills": ["java"],
    },
    {
        "platform": "Exercism",
        "external_id": "exercism_track_rust",
        "title": "Exercism Rust Track",
        "url": "https://exercism.org/tracks/rust",
        "difficulty": "Adaptive",
        "topics": ["Rust", "Language Track"],
        "language": "Rust",
        "description": "Practice and master Rust via the official Exercism track.",
        "source": "Exercism API (Track Reputation)",
        "skills": ["rust"],
    },
    {
        "platform": "Exercism",
        "external_id": "exercism_python_leap",
        "title": "Leap (Python)",
        "url": "https://exercism.org/tracks/python/exercises/leap",
        "difficulty": "Easy",
        "topics": ["bools", "Python"],
        "language": "Python",
        "description": "Practice bools, Python on the Exercism Python track.",
        "source": "Exercism Public Config",
        "skills": ["bools", "python"],
    },
    {
        "platform": "Exercism",
        "external_id": "exercism_python_triangle",
        "title": "Triangle (Python)",
        "url": "https://exercism.org/tracks/python/exercises/triangle",
        "difficulty": "Easy",
        "topics": ["bools", "Python"],
        "language": "Python",
        "description": "Practice bools, Python on the Exercism Python track.",
        "source": "Exercism Public Config",
        "skills": ["bools", "python"],
    },
    {
        "platform": "Exercism",
        "external_id": "exercism_javascript_line_up",
        "title": "Line Up (Javascript)",
        "url": "https://exercism.org/tracks/javascript/exercises/line-up",
        "difficulty": "Easy",
        "topics": ["numbers", "strings", "Javascript"],
        "language": "Javascript",
        "description": "Practice numbers, strings, Javascript on the Exercism Javascript track.",
        "source": "Exercism Public Config",
        "skills": ["numbers", "strings", "javascript"],
    },
    {
        "platform": "Exercism",
        "external_id": "exercism_java_relative_distance",
        "title": "Relative Distance (Java)",
        "url": "https://exercism.org/tracks/java/exercises/relative-distance",
        "difficulty": "Medium",
        "topics": ["maps", "Java"],
        "language": "Java",
        "description": "Practice maps, Java on the Exercism Java track.",
        "source": "Exercism Public Config",
        "skills": ["maps", "java"],
    },
    {
        "platform": "Exercism",
        "external_id": "exercism_rust_reverse_string",
        "title": "Reverse String (Rust)",
        "url": "https://exercism.org/tracks/rust/exercises/reverse-string",
        "difficulty": "Easy",
        "topics": ["iterators", "string-vs-str", "strings", "Rust"],
        "language": "Rust",
        "description": "Practice iterators, string-vs-str, strings, Rust on the Exercism Rust track.",
        "source": "Exercism Public Config",
        "skills": ["iterators", "string-vs-str", "strings", "rust"],
    },
    {
        "platform": "Exercism",
        "external_id": "exercism_rust_gigasecond",
        "title": "Gigasecond (Rust)",
        "url": "https://exercism.org/tracks/rust/exercises/gigasecond",
        "difficulty": "Easy",
        "topics": ["external-crates", "Rust"],
        "language": "Rust",
        "description": "Practice external-crates, Rust on the Exercism Rust track.",
        "source": "Exercism Public Config",
        "skills": ["external-crates", "rust"],
    },
    {
        "platform": "AtCoder",
        "external_id": "atcoder_abc086_a",
        "title": "Product",
        "url": "https://atcoder.jp/contests/abc086/tasks/abc086_a",
        "difficulty": "Easy",
        "topics": ["Math", "Beginner"],
        "language": "Any",
        "description": "Determine if the product of two integers is even or odd.",
        "source": "AtCoder Platform Reference",
        "skills": ["math", "beginner", "algorithms"],
    },
    {
        "platform": "CodeChef",
        "external_id": "cc_flow001",
        "title": "Add Two Numbers (FLOW001)",
        "url": "https://www.codechef.com/problems/FLOW001",
        "difficulty": "Easy",
        "topics": ["Math", "Fundamentals"],
        "language": "Python",
        "description": "Calculate the sum of two integers across multiple test cases.",
        "source": "CodeChef Practice Challenge",
        "skills": ["functions", "math", "problem-solving"],
    },
    {
        "platform": "CodeChef",
        "external_id": "cc_atm",
        "title": "ATM (ATM)",
        "url": "https://www.codechef.com/problems/ATM",
        "difficulty": "Easy",
        "topics": ["Conditionals", "Fundamentals"],
        "language": "Python",
        "description": "Pooja wants to withdraw X $US from an ATM. Calculate account balance after withdrawal.",
        "source": "CodeChef Practice Challenge",
        "skills": ["functions", "problem-solving"],
    },
    {
        "platform": "CodeChef",
        "external_id": "cc_tsort",
        "title": "Turbo Sort (TSORT)",
        "url": "https://www.codechef.com/problems/TSORT",
        "difficulty": "Easy",
        "topics": ["Sorting", "Arrays"],
        "language": "Python",
        "description": "Given a list of numbers, output numbers in non-decreasing order.",
        "source": "CodeChef Practice Challenge",
        "skills": ["arrays", "problem-solving"],
    },
    {
        "platform": "CodeChef",
        "external_id": "cc_luckfour",
        "title": "Lucky Four (LUCKFOUR)",
        "url": "https://www.codechef.com/problems/LUCKFOUR",
        "difficulty": "Easy",
        "topics": ["Iteration", "Strings", "Fundamentals"],
        "language": "Python",
        "description": "Count the occurrences of digit 4 in given integer inputs.",
        "source": "CodeChef Practice Challenge",
        "skills": ["iteration", "problem-solving"],
    },
    {
        "platform": "CodeChef",
        "external_id": "cc_flow006",
        "title": "Sum of Digits (FLOW006)",
        "url": "https://www.codechef.com/problems/FLOW006",
        "difficulty": "Easy",
        "topics": ["Math", "Iteration"],
        "language": "Python",
        "description": "Calculate the sum of digits of a given integer.",
        "source": "CodeChef Practice Challenge",
        "skills": ["iteration", "problem-solving"],
    },
    {
        "platform": "CodeChef",
        "external_id": "cc_conflip",
        "title": "Coin Flip (CONFLIP)",
        "url": "https://www.codechef.com/problems/CONFLIP",
        "difficulty": "Medium",
        "topics": ["Math", "Game Theory", "Algorithms"],
        "language": "Python",
        "description": "Determine the count of coins facing head or tail after N rounds of flipping.",
        "source": "CodeChef Practice Challenge",
        "skills": ["iteration", "problem-solving"],
    },
    {
        "platform": "CodeChef",
        "external_id": "cc_csub",
        "title": "Count Substrings (CSUB)",
        "url": "https://www.codechef.com/problems/CSUB",
        "difficulty": "Medium",
        "topics": ["Combinatorics", "Strings", "Arrays"],
        "language": "Python",
        "description": "Count the number of non-empty substrings starting and ending with 1.",
        "source": "CodeChef Practice Challenge",
        "skills": ["arrays", "problem-solving"],
    },
    {
        "platform": "CodeChef",
        "external_id": "cc_cleanup",
        "title": "Cleaning Up (CLEANUP)",
        "url": "https://www.codechef.com/problems/CLEANUP",
        "difficulty": "Medium",
        "topics": ["Arrays", "Sorting", "Greedy"],
        "language": "Python",
        "description": "Distribute unfinished jobs alternately between Chef and his assistant.",
        "source": "CodeChef Practice Challenge",
        "skills": ["arrays", "problem-solving"],
    },
    {
        "platform": "CodeChef",
        "external_id": "cc_marcha1",
        "title": "Paying up (MARCHA1)",
        "url": "https://www.codechef.com/problems/MARCHA1",
        "difficulty": "Medium",
        "topics": ["Recursion", "Bit Manipulation", "Subset Sum"],
        "language": "Python",
        "description": "Determine if a subset of banknotes sums up to the exact requested ransom amount.",
        "source": "CodeChef Practice Challenge",
        "skills": ["recursion", "problem-solving"],
    },
    {
        "platform": "CodeChef",
        "external_id": "cc_firesc",
        "title": "Fire Escape Routes (FIRESC)",
        "url": "https://www.codechef.com/problems/FIRESC",
        "difficulty": "Medium",
        "topics": ["Graph Algorithms", "DFS", "Connected Components"],
        "language": "Python",
        "description": "Find connected components and calculate escape routes in a friendship graph.",
        "source": "CodeChef Practice Challenge",
        "skills": ["graph-algorithms", "dfs"],
    },
    {
        "platform": "CodeChef",
        "external_id": "cc_prime1",
        "title": "Prime Generator (PRIME1)",
        "url": "https://www.codechef.com/problems/PRIME1",
        "difficulty": "Hard",
        "topics": ["Math", "Number Theory", "Sieve"],
        "language": "Python",
        "description": "Generate all prime numbers between two given numbers using segmented sieve.",
        "source": "CodeChef Practice Challenge",
        "skills": ["iteration", "problem-solving"],
    },
    {
        "platform": "CodeChef",
        "external_id": "cc_treeroot",
        "title": "Tree Root (TREEROOT)",
        "url": "https://www.codechef.com/problems/TREEROOT",
        "difficulty": "Hard",
        "topics": ["Tree Traversal", "Math", "Trees"],
        "language": "Python",
        "description": "Determine the root of a binary tree given node values and subtree sums.",
        "source": "CodeChef Practice Challenge",
        "skills": ["tree-traversal", "recursion"],
    },
    {
        "platform": "CodeChef",
        "external_id": "cc_digjump",
        "title": "Digit Jump (DIGJUMP)",
        "url": "https://www.codechef.com/problems/DIGJUMP",
        "difficulty": "Hard",
        "topics": ["Graph Algorithms", "BFS", "Shortest Path"],
        "language": "Python",
        "description": "Find minimum steps to jump from first to last index using digit matching graph BFS.",
        "source": "CodeChef Practice Challenge",
        "skills": ["graph-algorithms", "dfs"],
    },
    {
        "platform": "CodeChef",
        "external_id": "cc_mchef",
        "title": "MasterChef (MCHEF)",
        "url": "https://www.codechef.com/problems/MCHEF",
        "difficulty": "Hard",
        "topics": ["Dynamic Programming", "Knapsack", "Segment Tree"],
        "language": "Python",
        "description": "Optimize dish ratings under budget constraints using interval updates and dynamic programming.",
        "source": "CodeChef Practice Challenge",
        "skills": ["graph-algorithms", "recursion"],
    },
]


class ProblemMatcherService:
    """Matches and ranks practice problem recommendations with provenance."""

    def seed_problems(self, db: Session) -> list[Problem]:
        """Seed controlled problem references in PostgreSQL."""
        problems = []
        for p_def in CONTROLLED_PRACTICE_PROBLEMS:
            problem = db.query(Problem).filter(Problem.external_id == p_def["external_id"]).first()
            if not problem:
                problem = Problem(
                    platform=p_def["platform"],
                    external_id=p_def["external_id"],
                    title=p_def["title"],
                    url=p_def["url"],
                    difficulty=p_def["difficulty"],
                    topics={"items": p_def["topics"], "skills": p_def["skills"]},
                    language=p_def["language"],
                    description=p_def["description"],
                    source=p_def["source"],
                )
                db.add(problem)
                db.commit()
                db.refresh(problem)
            problems.append(problem)
        return problems

    def get_ranked_recommendations(
        self,
        user_id: str,
        target_skill_slug: str,
        db: Session,
        target_difficulty: Optional[str] = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Rank and return practice recommendations for a target skill with adaptive difficulty."""
        problems = self.seed_problems(db)

        # Derive target difficulty from SkillAssessment.mastery_score if not explicitly provided
        if not target_difficulty or target_difficulty == "Adaptive":
            from app.models.skill import Skill, SkillAssessment
            target_skill = db.query(Skill).filter(Skill.slug == target_skill_slug).first()
            mastery = 0.0
            if target_skill:
                ass = (
                    db.query(SkillAssessment)
                    .filter(
                        SkillAssessment.user_id == user_id,
                        SkillAssessment.skill_id == target_skill.id,
                    )
                    .order_by(SkillAssessment.evaluated_at.desc(), SkillAssessment.id.desc())
                    .first()
                )
                if ass:
                    mastery = ass.mastery_score

            if mastery < 30.0:
                target_difficulty = "Easy"
            elif mastery < 75.0:
                target_difficulty = "Medium"
            else:
                target_difficulty = "Hard"

        # Difficulty scale mapping for distance calculation
        DIFFICULTY_MAP = {
            "easy": 0,
            "medium": 1,
            "hard": 2,
            "adaptive": 0,
        }
        target_diff_val = DIFFICULTY_MAP.get(target_difficulty.lower(), 0)

        # Query completed internal attempts for user
        attempts = (
            db.query(CodeAttempt)
            .filter(CodeAttempt.user_id == user_id, CodeAttempt.status == "completed")
            .all()
        )
        completed_problem_ids = set(a.problem_id for a in attempts)

        # Query external solved evidence records for user
        ev_records = (
            db.query(Evidence)
            .filter(
                Evidence.user_id == user_id,
                Evidence.evidence_type == "problem_submission"
            )
            .all()
        )

        externally_solved_identifiers = set()
        for ev in ev_records:
            payload = ev.normalized_payload or {}
            raw_payload = ev.raw_payload or {}

            # CodeChef problem code
            codechef_code = payload.get("problem_code") or raw_payload.get("problem_code")
            if codechef_code:
                code_str = str(codechef_code).strip()
                externally_solved_identifiers.add(code_str.upper())
                externally_solved_identifiers.add(code_str.lower())
                externally_solved_identifiers.add(f"cc_{code_str.lower()}")

            # LeetCode / HackerRank / General slugs
            slug = payload.get("challenge_slug") or payload.get("title_slug") or payload.get("problem_slug") or payload.get("slug")
            if slug:
                slug_str = str(slug).strip().lower()
                externally_solved_identifiers.add(slug_str)

            # URL slug matching if present
            source_url = payload.get("source_url") or raw_payload.get("source_url") or ev.title
            if source_url:
                url_slug = source_url.rstrip("/").split("/")[-1].replace("problem", "").strip("/").lower()
                if url_slug:
                    externally_solved_identifiers.add(url_slug)

        # Query active platform connections for user to prioritize recommendations
        from app.models.platform import PlatformConnection
        active_conns = (
            db.query(PlatformConnection)
            .filter(PlatformConnection.user_id == user_id, PlatformConnection.connected == True)
            .all()
        )
        user_platforms = {c.platform for c in active_conns}

        recommendations = []
        for p in problems:
            # 1. Exclude internal completed CodeAttempt problems
            if p.id in completed_problem_ids:
                continue

            # 2. Exclude externally solved Evidence problems
            p_code = p.external_id.replace("cc_", "").replace("lc_", "").replace("hr_", "").strip().upper()
            p_url_slug = p.url.rstrip("/").split("/")[-1].replace("problem", "").strip("/").lower()
            p_ext_id = p.external_id.strip().lower()

            if (
                p_code in externally_solved_identifiers
                or p_url_slug in externally_solved_identifiers
                or p_ext_id in externally_solved_identifiers
            ):
                continue

            topics_dict = p.topics or {}
            skills_list = topics_dict.get("skills", [])

            if target_skill_slug in skills_list or target_skill_slug == "all":
                is_real_data = p.platform in external_platform_names()
                status_label = "REAL API DATA" if is_real_data else "PLANNED CONNECTOR"

                recommendations.append({
                    "problem_id": p.id,
                    "platform": p.platform,
                    "title": p.title,
                    "url": p.url,
                    "difficulty": p.difficulty,
                    "topics": topics_dict.get("items", []),
                    "target_skill_slug": target_skill_slug,
                    "reason": "Practice this skill on Exercism" if p.platform == "Exercism" else f"Builds verified {p.difficulty} skill evidence for {target_skill_slug.replace('-', ' ').title()}.",
                    "source": p.source,
                    "status_label": status_label,
                    "is_real_data": is_real_data,
                })

        # Multi-factor adaptive ranking:
        # Primary factor: Difficulty distance (lower is better, exact match = 0)
        # Secondary factor: Connected platform bonus (subtracts 0.5 from distance score if connected)
        def compute_rank_score(r: dict[str, Any]) -> float:
            prob_diff_str = str(r.get("difficulty", "Easy")).lower()
            prob_diff_val = DIFFICULTY_MAP.get(prob_diff_str, 0)
            diff_distance = abs(target_diff_val - prob_diff_val)
            platform_bonus = 0.5 if (r["platform"] in user_platforms) else 0.0
            return float(diff_distance) - platform_bonus

        recommendations.sort(key=compute_rank_score)
        return recommendations[:limit]


