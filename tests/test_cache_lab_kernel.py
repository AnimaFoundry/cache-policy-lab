"""Synthetic model checks and invalid-policy fault injection for Cache Policy Lab."""

from dataclasses import FrozenInstanceError
import unittest


from cache_policy_lab.kernel import Decision, FIFO, LRU, PolicyError, Request, TwoHit, simulate


class FixedPolicy:
    name = "fixed"

    def __init__(self, *decisions):
        self.decisions = iter(decisions)

    def decide(self, request, view):
        return next(self.decisions)


class KernelTests(unittest.TestCase):
    def test_hand_counted_weighted_lru(self):
        requests = [Request(key, size, 1) for key, size in
                    [("a", 3), ("b", 2), ("a", 3), ("c", 4), ("c", 4)]]
        result = simulate(requests, LRU(), capacity_tokens=5, history_slots=3)
        expected = {
            "requests": 5, "hits": 2, "misses": 3,
            "prefix_recompute_tokens": 9, "uncached_suffix_tokens": 5,
            "total_work_tokens": 14, "evictions": 2, "bypasses": 0,
            "peak_cached_tokens": 5, "peak_cache_entries": 2, "peak_history_slots": 3,
            "resource_budget_respected": True,
        }
        for key, value in expected.items():
            self.assertEqual(result[key], value, key)

    def test_two_hit_uses_previous_history_only(self):
        result = simulate([Request(key, 2, 0) for key in "aaabcb"], TwoHit(), 4, 2)
        self.assertEqual(result["hits"], 1)
        self.assertEqual(result["misses"], 5)
        self.assertEqual(result["bypasses"], 3)
        self.assertEqual(result["prefix_recompute_tokens"], 10)
        self.assertEqual(result["peak_cached_tokens"], 4)

    def test_history_expiration_prevents_second_hit_admission(self):
        result = simulate([Request(key, 1, 0) for key in "abca"], TwoHit(), 4, 2)
        self.assertEqual(result["bypasses"], 4)
        self.assertEqual(result["peak_cache_entries"], 0)

    def test_fifo_preserves_insertion_order_across_hits(self):
        requests = [Request(key, 1, 0) for key in "abacb"]
        self.assertEqual(simulate(requests, FIFO(), 2)["hits"], 2)
        self.assertEqual(simulate(requests, LRU(), 2)["hits"], 1)

    def test_oversized_prefix_bypasses_without_disturbing_cache(self):
        requests = [Request("a", 2, 0), Request("large", 8, 3), Request("a", 2, 0)]
        result = simulate(requests, LRU(), 2)
        self.assertEqual(result["hits"], 1)
        self.assertEqual(result["evictions"], 0)
        self.assertEqual(result["bypasses"], 1)
        self.assertEqual(result["total_work_tokens"], 13)

    def test_empty_input_has_zero_work(self):
        result = simulate(iter(()), LRU())
        self.assertEqual(result["requests"], 0)
        self.assertEqual(result["total_work_tokens"], 0)
        self.assertEqual(result["hit_rate"], 0.0)
        self.assertTrue(result["resource_budget_respected"])

    def test_iterator_is_not_advanced_before_decision(self):
        decided = []

        def events():
            for index in range(5):
                self.assertEqual(len(decided), index, "future request was consumed")
                yield Request(str(index), 1, 0)

        class Observer(LRU):
            name = "observer"

            def decide(self, request, view):
                decided.append(request.key)
                return super().decide(request, view)

        self.assertEqual(simulate(events(), Observer())["requests"], 5)

    def test_policy_receives_frozen_snapshot_and_current_event(self):
        test = self

        class Observer(LRU):
            name = "observer"

            def decide(self, request, view):
                test.assertIsInstance(view.cache, tuple)
                test.assertIsInstance(view.history, tuple)
                test.assertIsInstance(view.insertion_order, tuple)
                with test.assertRaises(FrozenInstanceError):
                    view.hit = True
                with test.assertRaises(FrozenInstanceError):
                    request.prefix_tokens = 0
                return super().decide(request, view)

        simulate([Request("a", 1), Request("a", 1)], Observer())

    def test_known_sizes_are_checked_after_eviction_and_history_expiration(self):
        requests = [Request("a", 1), Request("b", 1), Request("c", 1), Request("a", 2)]
        with self.assertRaisesRegex(ValueError, "one token size"):
            simulate(requests, LRU(), 1, 1)

    def test_resource_exclusions_are_explicit(self):
        result = simulate([Request(str(index), 1, 0) for index in range(8)], LRU(), 2, 1)
        self.assertEqual(result["peak_cache_entries"], 2)
        self.assertEqual(result["peak_history_slots"], 1)
        self.assertEqual(result["accounting"]["validation_registry_entries"], 8)
        for name in ("validation_registry_budgeted", "python_heap_measured",
                     "policy_cpu_measured", "policy_state_budgeted",
                     "snapshot_storage_budgeted", "policy_execution_sandboxed"):
            self.assertIs(result["accounting"][name], False)

    def test_invalid_request_types_and_values(self):
        for key in ("", "a b", "https://example.invalid", "x" * 129, 1, True, "你好"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                Request(key, 1)
        for prefix in (0, -1, True, 1.0, "1"):
            with self.subTest(prefix=prefix), self.assertRaises(ValueError):
                Request("a", prefix)
        for suffix in (-1, False, 1.0, "1"):
            with self.subTest(suffix=suffix), self.assertRaises(ValueError):
                Request("a", 1, suffix)
        with self.assertRaises(ValueError):
            simulate([{"key": "a", "prefix_tokens": 1}], LRU())

    def test_invalid_capacity_types_and_values(self):
        for value in (0, -1, True, False, 1.0, "1"):
            with self.subTest(capacity=value), self.assertRaises(ValueError):
                simulate([], LRU(), capacity_tokens=value)
            with self.subTest(history=value), self.assertRaises(ValueError):
                simulate([], LRU(), history_slots=value)

    def test_over_budget_policy_is_rejected(self):
        with self.assertRaisesRegex(PolicyError, "exceed"):
            simulate([Request("a", 2), Request("b", 2)],
                     FixedPolicy(Decision(True), Decision(True)), 2)

    def test_oversized_admission_is_rejected(self):
        with self.assertRaisesRegex(PolicyError, "exceed"):
            simulate([Request("a", 3)], FixedPolicy(Decision(True)), 2)

    def test_nonexistent_and_duplicate_evictions_are_rejected(self):
        for evictions in (("missing",), ("a", "a")):
            with self.subTest(evictions=evictions), self.assertRaises(PolicyError):
                simulate([Request("a", 1), Request("b", 1)],
                         FixedPolicy(Decision(True), Decision(True, evictions)), 1)

    def test_hit_action_cannot_remove_or_readmit_cached_entry(self):
        for action in (Decision(True), Decision(True, ("a",)), Decision(False, ("a",))):
            with self.subTest(action=action), self.assertRaises(PolicyError):
                simulate([Request("a", 1), Request("a", 1)],
                         FixedPolicy(Decision(True), action), 2)

    def test_bypass_cannot_remove_entries(self):
        with self.assertRaisesRegex(PolicyError, "bypass"):
            simulate([Request("a", 1), Request("b", 1)],
                     FixedPolicy(Decision(True), Decision(False, ("a",))), 2)

    def test_invalid_decision_shapes_are_rejected(self):
        for action in (None, {"admit": True}, Decision(1), Decision(False, []),
                       Decision(False, (True,))):
            with self.subTest(action=action), self.assertRaises(PolicyError):
                simulate([Request("a", 1)], FixedPolicy(action))

    def test_policy_failure_does_not_return_a_partial_report(self):
        with self.assertRaisesRegex(PolicyError, "event 2"):
            simulate([Request("a", 1), Request("b", 1)], FixedPolicy(Decision(True)))

if __name__ == "__main__":
    unittest.main()
