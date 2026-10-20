"""Illustrative pricing and latency model.

All money is tracked as integer micro-dollars (1 USD = 1_000_000 µ$) so the
ledger never accumulates floating-point drift. A price quoted in
"USD per million tokens" is numerically equal to "µ$ per token", which keeps
the arithmetic trivial.

Prices here are illustrative, not any specific provider's rate card.
"""

from __future__ import annotations

from dataclasses import dataclass

MICROS_PER_USD = 1_000_000


def to_micros(usd: float) -> int:
    return round(usd * MICROS_PER_USD)


def to_usd(micros: int) -> float:
    return micros / MICROS_PER_USD


@dataclass(frozen=True)
class Price:
    input_usd_per_mtok: float = 3.0
    output_usd_per_mtok: float = 15.0

    def cost_micros(self, input_tokens: int, output_tokens: int) -> int:
        return round(
            input_tokens * self.input_usd_per_mtok
            + output_tokens * self.output_usd_per_mtok
        )


def model_latency_s(output_tokens: int, base_s: float = 1.5, tokens_per_s: float = 80.0) -> float:
    """Time-to-first-token plus generation time."""
    return base_s + output_tokens / tokens_per_s
