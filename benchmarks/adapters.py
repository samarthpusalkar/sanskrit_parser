from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, List, Sequence

from .models import AdapterCapabilities, BenchmarkCase, BenchmarkResult


class BenchmarkAdapter(ABC):
    """Abstract contract for benchmarkable Paninian engines."""

    name: str

    @abstractmethod
    def supported_domains(self) -> Sequence[str]:
        raise NotImplementedError

    @abstractmethod
    def capabilities(self) -> AdapterCapabilities:
        raise NotImplementedError

    @abstractmethod
    def list_loaded_rules(self) -> List[str]:
        raise NotImplementedError

    @abstractmethod
    def run_case(self, case: BenchmarkCase) -> BenchmarkResult:
        raise NotImplementedError

    def batch_run(self, cases: Iterable[BenchmarkCase]) -> List[BenchmarkResult]:
        return [self.run_case(case) for case in cases]
