"""
11D Morphological Tensor Coordinate Schema.

Encodes Sanskrit sub-words into formal dense 11D integer coordinate vectors:
[root_id, pos_id, upasarga_id, affix1_id, affix2_id, lakara_id, voice_id, purusa_id, vacana_id, case_id, gender_id]
"""

from dataclasses import dataclass
from typing import List, Any


@dataclass
class TensorDelta:
    """Represents a surgical modification matrix (delta) for a TensorCoordinate."""
    vector: List[int]

    def __post_init__(self):
        if len(self.vector) != 11:
            raise ValueError(f"TensorDelta must be exactly 11D, got {len(self.vector)}D.")


class TensorCoordinate:
    """Represents an 11-dimensional morphological Pāṇinian integer vector."""

    def __init__(self, vector: List[int]):
        if len(vector) != 11:
            raise ValueError(f"TensorCoordinate must be exactly 11D, got {len(vector)}D.")
        self.vector = list(vector)

    @property
    def root_id(self) -> int: return self.vector[0]
    @property
    def pos_id(self) -> int: return self.vector[1]
    @property
    def upasarga_id(self) -> int: return self.vector[2]
    @property
    def affix1_id(self) -> int: return self.vector[3]
    @property
    def affix2_id(self) -> int: return self.vector[4]
    @property
    def lakara_id(self) -> int: return self.vector[5]
    @property
    def voice_id(self) -> int: return self.vector[6]
    @property
    def purusa_id(self) -> int: return self.vector[7]
    @property
    def vacana_id(self) -> int: return self.vector[8]
    @property
    def case_id(self) -> int: return self.vector[9]
    @property
    def gender_id(self) -> int: return self.vector[10]

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, TensorCoordinate): return False
        return self.vector == other.vector

    def __add__(self, delta: TensorDelta) -> 'TensorCoordinate':
        if not isinstance(delta, TensorDelta): raise TypeError("Can only add TensorDelta.")
        new_vec = [v + d for v, d in zip(self.vector, delta.vector)]
        return TensorCoordinate(new_vec)

    def __sub__(self, delta: TensorDelta) -> 'TensorCoordinate':
        if not isinstance(delta, TensorDelta): raise TypeError("Can only subtract TensorDelta.")
        new_vec = [v - d for v, d in zip(self.vector, delta.vector)]
        return TensorCoordinate(new_vec)

    def __repr__(self) -> str:
        return f"TensorCoordinate({self.vector})"
