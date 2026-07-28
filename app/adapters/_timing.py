"""Замер длительности стадии речевого конвейера.

Каждый адаптер обязан вернуть, сколько он занял. Из этих чисел складывается бюджет
пилота (≤ 2.5 с p95 от кнопки до звука) и цифры для отчёта инвестору, поэтому
меряем реально, а не оцениваем.
"""

import time
from collections.abc import Iterator
from contextlib import contextmanager


class Elapsed:
    """Мутируемый держатель результата: заполняется на выходе из контекста."""

    __slots__ = ("ms",)

    def __init__(self) -> None:
        self.ms = 0


@contextmanager
def measure() -> Iterator[Elapsed]:
    """Замерить время блока в миллисекундах.

    >>> with measure() as took:
    ...     ...
    >>> took.ms
    """
    started = time.perf_counter()
    result = Elapsed()
    try:
        yield result
    finally:
        result.ms = int((time.perf_counter() - started) * 1000)
