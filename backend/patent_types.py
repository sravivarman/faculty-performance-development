"""Supported patent types; Copyright is its own type, never Other."""
from typing import Literal

PatentType = Literal['UTILITY', 'DESIGN', 'COPYRIGHT']
PATENT_TYPES = {'UTILITY': 'Utility', 'DESIGN': 'Design', 'COPYRIGHT': 'Copyright'}
