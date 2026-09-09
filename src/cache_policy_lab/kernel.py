"""An event-at-a-time, token-budgeted prefix-cache experiment kernel.

The engine measures prefix recomputation on cache misses and an uncached suffix
on every request. These are model units, not measured time or device memory.
Only resident prefix tokens and previous-request history slots are budgeted.
Python heap use, snapshots, policy state, and the ever-seen key-size validation
index are outside those budgets. Custom Python policies are trusted code: the
immutable current-event interface is not a sandbox or a proof against cheating.
"""

from __future__ import annotations

from collections import OrderedDict, deque
from dataclasses import dataclass
import re
from typing import Iterable, Protocol


_KEY_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z", re.ASCII)


def _integer(value: object, minimum: int, name: str) -> None:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}; booleans are invalid")


def _key(value: object) -> None:
    if type(value) is not str or _KEY_PATTERN.fullmatch(value) is None:
        raise ValueError("key must be an opaque ASCII ID of 1..128 letters, digits, . _ : or -")


@dataclass(frozen=True, slots=True)
class Request:
    """A current request with an opaque, consistently sized prefix identifier."""

    key: str
    prefix_tokens: int
    suffix_tokens: int = 16

    def __post_init__(self) -> None:
        _key(self.key)
        _integer(self.prefix_tokens, 1, "prefix_tokens")
        _integer(self.suffix_tokens, 0, "suffix_tokens")


@dataclass(frozen=True, slots=True)
class View:
    """Immutable state before the current decision; cache order is LRU first.

    History contains only the previous requests, with oldest keys first.
    Insertion order is provided separately so FIFO needs no private state.
    """

    cache: tuple[tuple[str, int], ...]
    history: tuple[str, ...]
    capacity_tokens: int
    history_slots: int
    hit: bool
    insertion_order: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Decision:
    """On a miss, optionally admit after removing existing, distinct entries.

    Hits and bypasses must use ``Decision(False)``. The engine refreshes LRU
    order on a hit; FIFO insertion order changes only on admission or eviction.
    Decisions are checked at the engine boundary, before changing its state.
    """

    admit: bool
    evict: tuple[str, ...] = ()


class PolicyError(ValueError):
    """The policy returned an invalid or over-budget action."""


class Policy(Protocol):
    name: str

    def decide(self, request: Request, view: View) -> Decision: ...


def _admit(request: Request, view: View, order: tuple[str, ...]) -> Decision:
    if view.hit or request.prefix_tokens > view.capacity_tokens:
        return Decision(False)
    sizes = dict(view.cache)
    resident = sum(sizes.values())
    removed: list[str] = []
    for key in order:
        if resident + request.prefix_tokens <= view.capacity_tokens:
            break
        resident -= sizes[key]
        removed.append(key)
    return Decision(True, tuple(removed))


class LRU:
    """Demand admission and least-recently-used eviction, weighted by tokens."""

    name = "lru"

    def decide(self, request: Request, view: View) -> Decision:
        return _admit(request, view, tuple(key for key, _ in view.cache))


class TwoHit:
    """LRU eviction; admit misses only if present in the bounded prior history."""

    name = "two_hit"

    def decide(self, request: Request, view: View) -> Decision:
        if request.key not in view.history:
            return Decision(False)
        return _admit(request, view, tuple(key for key, _ in view.cache))


class FIFO:
    """Demand admission and oldest-admitted-first eviction."""

    name = "fifo"

    def decide(self, request: Request, view: View) -> Decision:
        return _admit(request, view, view.insertion_order)


def _check_decision(
    decision: object, request: Request, view: View, resident: int,
) -> Decision:
    if type(decision) is not Decision:
        raise PolicyError("decide must return a Decision")
    if type(decision.admit) is not bool:
        raise PolicyError("Decision.admit must be a boolean")
    if type(decision.evict) is not tuple:
        raise PolicyError("Decision.evict must be a tuple of distinct cached keys")
    if any(type(key) is not str for key in decision.evict):
        raise PolicyError("eviction keys must be strings")
    if len(set(decision.evict)) != len(decision.evict):
        raise PolicyError("duplicate eviction keys are invalid")
    sizes = dict(view.cache)
    if any(key not in sizes for key in decision.evict):
        raise PolicyError("cannot evict a key that is not cached")
    if view.hit and (decision.admit or decision.evict):
        raise PolicyError("a hit must return Decision(False) without evictions")
    if not decision.admit and decision.evict:
        raise PolicyError("a bypass must not evict entries")
    if decision.admit:
        remaining = resident - sum(sizes[key] for key in decision.evict)
        if remaining + request.prefix_tokens > view.capacity_tokens:
            raise PolicyError("admission would exceed the prefix-token capacity")
    return decision


def simulate(
    requests: Iterable[Request],
    policy: Policy,
    capacity_tokens: int = 768,
    history_slots: int = 64,
) -> dict:
    """Consume and decide each request before advancing the iterable again.

    Policies receive only the current request and an immutable state snapshot.
    The engine owns all cache/history updates and accounting. A repeated key
    must keep its prefix size, even after eviction or history expiration; this
    uses a disclosed, unbounded validation index outside the policy budgets.
    An invalid request or decision fails the run instead of returning metrics.
    """
    _integer(capacity_tokens, 1, "capacity_tokens")
    _integer(history_slots, 1, "history_slots")
    if not callable(getattr(policy, "decide", None)):
        raise ValueError("policy must expose decide(request, view)")
    name = getattr(policy, "name", None)
    if type(name) is not str or not name or len(name) > 128:
        raise ValueError("policy.name must be a nonempty string of at most 128 characters")

    cache: OrderedDict[str, int] = OrderedDict()
    insertion_order: OrderedDict[str, None] = OrderedDict()
    history: deque[str] = deque(maxlen=history_slots)
    known_sizes: dict[str, int] = {}
    resident = peak_resident = peak_entries = peak_history = 0
    count = hits = misses = evictions = bypasses = prefix_work = suffix_work = 0

    for request in requests:
        if type(request) is not Request:
            raise ValueError("each input event must be a Request")
        # Frozen data is an interface convenience, not a Python security boundary.
        request.__post_init__()
        if request.key in known_sizes and known_sizes[request.key] != request.prefix_tokens:
            raise ValueError("one prefix key must have one token size throughout a run")
        known_sizes[request.key] = request.prefix_tokens
        hit = request.key in cache
        view = View(
            cache=tuple(cache.items()), history=tuple(history),
            capacity_tokens=capacity_tokens, history_slots=history_slots,
            hit=hit, insertion_order=tuple(insertion_order),
        )
        try:
            raw_decision = policy.decide(request, view)
        except Exception as error:
            raise PolicyError(f"policy decide failed at event {count + 1}") from error
        decision = _check_decision(raw_decision, request, view, resident)

        count += 1
        suffix_work += request.suffix_tokens
        if hit:
            hits += 1
            cache.move_to_end(request.key)
        else:
            misses += 1
            prefix_work += request.prefix_tokens
            if decision.admit:
                for key in decision.evict:
                    resident -= cache.pop(key)
                    del insertion_order[key]
                    evictions += 1
                cache[request.key] = request.prefix_tokens
                insertion_order[request.key] = None
                resident += request.prefix_tokens
            else:
                bypasses += 1
        history.append(request.key)
        # Check actual engine state after every event, independently of policy.
        if not (
            resident == sum(cache.values())
            and 0 <= resident <= capacity_tokens
            and len(history) <= history_slots
            and set(cache) == set(insertion_order)
        ):
            raise PolicyError("engine resource invariant failed")
        peak_resident = max(peak_resident, resident)
        peak_entries = max(peak_entries, len(cache))
        peak_history = max(peak_history, len(history))

    return {
        "policy": name,
        "requests": count,
        "hits": hits,
        "misses": misses,
        "hit_rate": hits / count if count else 0.0,
        "prefix_recompute_tokens": prefix_work,
        "uncached_suffix_tokens": suffix_work,
        "total_work_tokens": prefix_work + suffix_work,
        "evictions": evictions,
        "bypasses": bypasses,
        "peak_cached_tokens": peak_resident,
        "peak_cache_entries": peak_entries,
        "peak_history_slots": peak_history,
        "capacity_tokens": capacity_tokens,
        "history_capacity_slots": history_slots,
        "resource_budget_respected": True,
        "resource_model": "prefix-token-capacity-and-bounded-request-history-v1",
        "accounting": {
            "prefix_work": "prefix_tokens on each cache miss",
            "suffix_work": "suffix_tokens on every request; never cached",
            "cache_capacity_unit": "modeled resident prefix tokens",
            "history_capacity_unit": "previous-request key slots",
            "validation_registry_entries": len(known_sizes),
            "validation_registry_budgeted": False,
            "python_heap_measured": False,
            "policy_cpu_measured": False,
            "policy_state_budgeted": False,
            "snapshot_storage_budgeted": False,
            "policy_execution_sandboxed": False,
        },
    }
