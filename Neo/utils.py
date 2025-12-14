"""
Neo Utils Module
Utility functions for the Neo package.
"""

import re


def clean_json_response(text: str) -> str:
    """
    Cleans Gemini response to ensure valid JSON parsing.
    Removes Markdown fences and attempts to fix common escape issues.
    """
    # 1. Remove Markdown code blocks
    text = re.sub(r"^```json\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^```\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"```$", "", text, flags=re.MULTILINE)

    # 2. Fix simple invalid escapes (e.g., \d in strings -> \\d)
    # This matches a backslash NOT followed by a valid escape char (", \, /, b, f, n, r, t, u)
    # and doubles it. This prevents "Invalid \escape" errors.
    text = re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", text)

    return text.strip()
