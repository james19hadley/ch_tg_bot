import re

def has_chinese(text: str) -> bool:
    """Checks if the text contains at least one Chinese character."""
    return bool(re.search(r'[\u4e00-\u9fff]', text))
