from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Item:
    path: Path
    name: str
    locator: str
    revision: str = "current"


@dataclass
class Collection:
    items: list[Item] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    absent: list[str] = field(default_factory=list)
    checkpoint: dict = field(default_factory=dict)
    complete: bool = True
