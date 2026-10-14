from dataclasses import dataclass, replace
from typing import Self


@dataclass(frozen=True)
class CaptureProgress:
    total_pages: int
    captured_pages: frozenset[int] = frozenset()

    def __post_init__(self) -> None:
        if type(self.total_pages) is not int or self.total_pages < 1:
            raise ValueError("O total de páginas da captura é inválido.")

        if not all(self._is_valid_page(number) for number in self.captured_pages):
            raise ValueError("O registro contém números de página inválidos.")

    @property
    def is_complete(self) -> bool:
        return len(self.captured_pages) == self.total_pages

    def with_page(self, number: int) -> Self:
        return replace(self, captured_pages=self.captured_pages | {number})

    def _is_valid_page(self, number: object) -> bool:
        return type(number) is int and 1 <= number <= self.total_pages
