from dataclasses import dataclass
from typing import Any
from enum import Enum

@dataclass
class Table:
    name: str
    description: str

@dataclass
class data:
    dtype: Any
    unit: str | None = None


@dataclass
class Table:
    name: str
    description: str
    keywords: str
    time_range: str
    preview_data: str


