from mcp.server.fastmcp import FastMCP

# Initialize FastMCP Server
mcp = FastMCP("GeminiInterviewerMCP")

@mcp.tool()
def validate_python_syntax(code: str) -> str:
    """Validates the syntax of a Python code snippet submitted by the user.
    
    Args:
        code: Python code block to validate.
    """
    try:
        compile(code, "<string>", "exec")
        return "Success: Python code syntax is valid."
    except SyntaxError as e:
        return f"Error: Syntax error on line {e.lineno}: {e.msg}"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def get_study_resources(topic: str) -> str:
    """Returns curated learning resources and documentation links for a given technical topic.
    
    Args:
        topic: The technical skill or topic area (e.g., 'Recursion', 'SQL Joins').
    """
    resources = {
        "recursion": "1. GeeksforGeeks Recursion: https://www.geeksforgeeks.org/recursion/\n2. Python RealPython Recursion: https://realpython.com/python-thinking-recursively/",
        "sql joins": "1. W3Schools SQL Joins: https://www.w3schools.com/sql/sql_join.asp\n2. SQLBolt Joins Tutorial: https://sqlbolt.com/lesson/select_queries_with_joins",
        "system design": "1. System Design Primer: https://github.com/donnemartin/system-design-primer\n2. ByteByteGo: https://bytebytego.com/",
        "concurrency": "1. Python Threading/Multiprocessing docs: https://docs.python.org/3/library/concurrency.html\n2. RealPython Concurrency: https://realpython.com/python-concurrency/",
        "dynamic programming": "1. MIT Dynamic Programming Lecture: https://ocw.mit.edu/\n2. LeetCode DP Study Plan: https://leetcode.com/study-plan/dynamic-programming/"
    }
    
    key = topic.lower().strip()
    for k, v in resources.items():
        if k in key or key in k:
            return f"Curated Resources for {topic}:\n{v}"
            
    return f"Resources for {topic}:\n1. Official Python Documentation: https://docs.python.org/\n2. MDN Web Docs (for web tech): https://developer.mozilla.org/\n3. Coursera / edX search for: {topic}"

@mcp.tool()
def suggest_practice_challenges(role: str, difficulty: str) -> str:
    """Suggests LeetCode / HackerRank-like challenge topics and descriptions matching a target role and difficulty.
    
    Args:
        role: The target role (e.g., 'Software Engineer', 'Data Analyst').
        difficulty: The desired challenge difficulty level ('easy', 'medium', or 'hard').
    """
    challenges = {
        "easy": [
            "Two Sum (Array / Hash Map manipulation)",
            "Valid Parentheses (Stack operations)",
            "Merge Two Sorted Lists (Linked list traversal)"
        ],
        "medium": [
            "Container With Most Water (Two-pointer technique)",
            "Longest Substring Without Repeating Characters (Sliding window)",
            "Binary Tree Level Order Traversal (BFS / Queue)"
        ],
        "hard": [
            "Merge k Sorted Lists (Divide & Conquer / Min Heap)",
            "Trapping Rain Water (Two-pointer / Stack)",
            "Edit Distance (Dynamic programming)"
        ]
    }
    diff = difficulty.lower().strip()
    if diff not in challenges:
        diff = "medium"
        
    ch_list = challenges[diff]
    res = f"Recommended Practice Challenges ({difficulty.upper()} level for {role}):\n"
    for idx, ch in enumerate(ch_list):
        res += f"{idx+1}. {ch}\n"
    return res

if __name__ == "__main__":
    mcp.run()
