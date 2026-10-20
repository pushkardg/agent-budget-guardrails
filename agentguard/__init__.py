"""agentguard: budget guardrails for autonomous agents, with a simulator to test them."""

from .breaker import CircuitBreaker
from .controllers import Layered, LayeredConfig, MonthlyBudgetAlert, NoGuard, StaticTokenCap
from .ledger import BudgetExceeded, Ledger, ReservationNotHeld
from .pricing import Price
from .sim import Simulator, Step
from .stop import StopMode, StopToken
from .velocity import NoveltyTracker, SpendWindow

__all__ = [
    "BudgetExceeded", "CircuitBreaker", "Layered", "LayeredConfig", "Ledger",
    "MonthlyBudgetAlert", "NoGuard", "NoveltyTracker", "Price", "ReservationNotHeld", "Simulator",
    "SpendWindow", "StaticTokenCap", "Step", "StopMode", "StopToken",
]
__version__ = "0.1.0"
