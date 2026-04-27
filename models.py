from dataclasses import dataclass, field
from typing import List

@dataclass
class Task:
    text: str
    completed: bool = False
    priority: str = "medium"  # high | medium | low
    tags: List[str] = field(default_factory=list)
