import pytest

from agentguard import (
    BudgetExceeded, CircuitBreaker, Layered, Ledger, NoGuard, NoveltyTracker,
    SpendWindow, StaticTokenCap, StopMode, StopToken,
)
from agentguard.bench import run_all
from agentguard.scenarios import SCENARIOS, Scenario
from agentguard.sim import Simulator, Step

SC = {s.name: s for s in SCENARIOS}


# --- ledger --------------------------------------------------------------

def test_reservation_must_fit_every_level():
    led = Ledger()
    led.open("tenant", 100)
    led.open("root", 80, "tenant")
    led.open("child", 50, "root")
    led.reserve("child", 40, "r1")
    with pytest.raises(BudgetExceeded) as e:
        led.reserve("child", 20, "r2")
    assert e.value.key == "child"
    led.reserve("root", 30, "r3")  # root now 70/80 held
    with pytest.raises(BudgetExceeded) as e:
        led.reserve("root", 20, "r4")
    assert e.value.key == "root"


def test_settle_and_release_are_idempotent():
    led = Ledger()
    led.open("t", 100)
    led.reserve("t", 30, "r")
    assert led.reserve("t", 30, "r").amount == 30  # retry returns same hold
    assert led.budgets["t"].reserved == 30
    assert led.settle("r", 10) is True
    assert led.settle("r", 10) is False
    assert led.spent("t") == 10 and led.budgets["t"].reserved == 0
    led.reserve("t", 20, "r2")
    assert led.release("r2") is True and led.release("r2") is False
    assert led.headroom("t") == 90


def test_overrun_is_recorded():
    led = Ledger()
    led.open("t", 100)
    led.reserve("t", 10, "r")
    led.settle("r", 15)
    assert led.overrun_micros == 5


# --- signals -------------------------------------------------------------

def test_spend_window_evicts():
    w = SpendWindow(60)
    w.add(0, 600)
    w.add(30, 600)
    assert w.rate_per_min(30) == 1200
    assert w.rate_per_min(61) == 600


def test_novelty_separates_loops_from_progress():
    loop, work, cycle = NoveltyTracker(20, 10), NoveltyTracker(20, 10), NoveltyTracker(20, 10)
    for i in range(20):
        loop.add("call:x")
        work.add(f"file:{i}")
        cycle.add(f"plan:{'ABC'[i % 3]}")
    assert loop.ratio() == pytest.approx(0.05)
    assert work.ratio() == 1.0
    assert cycle.ratio() < 0.4
    assert NoveltyTracker(20, 10).ratio() is None


def test_circuit_breaker_lifecycle():
    b = CircuitBreaker(failure_threshold=3, window_s=60, cooldown_s=100)
    for t in (0, 1, 2):
        assert b.allow(t)
        b.record_failure(t)
    assert b.state == "open" and not b.allow(50)
    assert b.allow(103) and b.state == "half_open"
    assert not b.allow(104)  # only one trial
    b.record_failure(105)
    assert b.state == "open"
    assert b.allow(206)
    b.record_success(206)
    assert b.state == "closed"


def test_stop_token_first_request_wins():
    tok = StopToken()
    tok.request("hard", StopMode.HARD, 1)
    tok.request("soft", StopMode.GRACEFUL, 2)
    assert tok.requested.mode is StopMode.HARD


# --- simulator + controllers ---------------------------------------------

def test_hard_kill_orphans_and_graceful_stop_rolls_back():
    hard = Simulator(SC["long_task"], StaticTokenCap()).run()
    assert hard.orphaned == 1 and hard.stopped_runs == 1
    graceful = Simulator(SC["recursive_spawn"], Layered()).run()
    assert graceful.orphaned == 0 and graceful.compensated > 0


def test_layered_never_kills_legit_work():
    for name in ("normal_task", "long_task", "parallel_batch"):
        r = Simulator(SC[name], Layered()).run()
        assert r.work_completed, name
        assert r.orphaned == 0


def test_layered_contains_every_runaway_quickly():
    for name in ("tool_retry_loop", "recursive_spawn", "nonconverging_plan"):
        r = Simulator(SC[name], Layered()).run()
        assert not r.hit_horizon and r.spawn_capped == 0, name
        assert r.time_to_contain_s is not None and r.time_to_contain_s < 300, name
        assert r.runaway_cost < 5_500_000, name  # under ~$5.50


def test_unguarded_runaways_run_to_horizon_or_cap():
    for name in ("tool_retry_loop", "nonconverging_plan"):
        assert Simulator(SC[name], NoGuard()).run().hit_horizon
    assert Simulator(SC["recursive_spawn"], NoGuard()).run().spawn_capped > 0


def test_per_run_caps_do_not_see_fan_out():
    r = Simulator(SC["recursive_spawn"], StaticTokenCap()).run()
    assert r.stopped_runs == 0 and r.spawn_capped > 0


def test_ledger_spend_matches_simulated_spend():
    ctl = Layered()
    r = Simulator(SC["parallel_batch"], ctl).run()
    assert ctl.ledger.spent("tenant:acme") == r.total_cost
    assert ctl.ledger.budgets["tenant:acme"].reserved == 0


def test_benchmark_is_deterministic():
    a = [(x.scenario, x.controller, x.total_cost) for x in run_all()]
    b = [(x.scenario, x.controller, x.total_cost) for x in run_all()]
    assert a == b


def test_custom_scenario():
    def script():
        for i in range(3):
            yield Step(f"s{i}", 1000, 100)
    r = Simulator(Scenario("tiny", "", True, script), Layered()).run()
    assert r.work_completed and r.steps_done == 3


# --- v2, variants, billing --------------------------------------------------

from agentguard.controllers import layered_v2_config
from agentguard.robustness import contained
from agentguard.variants import FAMILIES

FAM = {f.name: f for f in FAMILIES}


def _v2():
    return Layered(layered_v2_config(), name="layered_v2")


def test_variants_are_deterministic_per_seed():
    for fam in FAMILIES:
        a = Simulator(fam.make(7), Layered()).run()
        b = Simulator(fam.make(7), Layered()).run()
        assert (a.total_cost, a.ended_at) == (b.total_cost, b.ended_at), fam.name


def test_v2_fixes_v1_failures():
    for seed in range(1000, 1005):
        assert not Simulator(FAM["polling"].make(seed), Layered()).run().work_completed
        assert Simulator(FAM["polling"].make(seed), _v2()).run().work_completed
        assert not Simulator(FAM["wide_batch"].make(seed), Layered()).run().work_completed
        assert Simulator(FAM["wide_batch"].make(seed), _v2()).run().work_completed
        assert not contained(Simulator(FAM["long_cycle"].make(seed), Layered()).run())
        assert contained(Simulator(FAM["long_cycle"].make(seed), _v2()).run())


def test_v2_has_its_own_known_failures():
    # Documented in the README: each fix moved the boundary.
    for seed in range(1000, 1005):
        assert not Simulator(FAM["deep_delegation"].make(seed), _v2()).run().work_completed
        assert not contained(Simulator(FAM["stuck_poll"].make(seed), _v2()).run())
        assert not contained(Simulator(FAM["slow_drip"].make(seed), _v2()).run())


def test_v2_run_ceiling_is_respected():
    ctl = _v2()
    Simulator(FAM["long_cycle"].make(1000), ctl).run()
    for key, b in ctl.ledger.budgets.items():
        if key.startswith("run:"):
            assert b.limit <= 100_000_000


def test_stopped_cost_accounting():
    r = Simulator(SC["recursive_spawn"], Layered()).run()
    assert 0 < r.stopped_cost <= r.total_cost
    assert r.aborted_cost <= r.stopped_cost


# --- production concerns: concurrency, crashes, late settles ----------------

import threading


def test_concurrent_reservations_never_overshoot():
    led = Ledger()
    led.open("tenant", 1_000)
    led.open("root", 600, "tenant")
    for i in range(8):
        led.open(f"child{i}", None, "root")
    granted = []
    lock = threading.Lock()

    def worker(i):
        for j in range(200):
            try:
                led.reserve(f"child{i}", 7, f"r{i}-{j}")
                with lock:
                    granted.append(7)
            except BudgetExceeded:
                pass

    ts = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert sum(granted) <= 600
    assert led.budgets["root"].reserved == sum(granted)
    assert led.budgets["tenant"].reserved == sum(granted)


def test_crashed_caller_hold_expires_and_frees_budget():
    led = Ledger()
    led.open("t", 100)
    led.reserve("t", 80, "crashed", now=0, ttl_s=30)
    with pytest.raises(BudgetExceeded):
        led.reserve("t", 50, "next", now=10, ttl_s=30)
    assert led.sweep_expired(now=29) == []
    assert led.sweep_expired(now=30) == ["crashed"]
    assert led.headroom("t") == 100
    led.reserve("t", 50, "next", now=31, ttl_s=30)


def test_late_settle_after_expiry_still_records_spend():
    led = Ledger()
    led.open("t", 100)
    led.reserve("t", 40, "slow", now=0, ttl_s=10)
    led.sweep_expired(now=11)
    assert led.settle("slow", 35) is True
    assert led.spent("t") == 35 and led.budgets["t"].reserved == 0
    assert led.late_settles == 1
    assert led.settle("slow", 35) is False  # still idempotent


def test_v3_trades_deep_delegation_for_costlier_recursion_stops():
    from agentguard.controllers import layered_v3_config
    for seed in range(2000, 2005):
        v2 = Simulator(FAM["recursive_var"].make(seed), _v2()).run()
        v3 = Simulator(FAM["recursive_var"].make(seed), Layered(layered_v3_config())).run()
        assert contained(v3) and v3.runaway_cost > v2.runaway_cost
        assert Simulator(FAM["deep_delegation"].make(seed), Layered(layered_v3_config())).run().work_completed


def test_renewed_lease_survives_sweep_and_expired_lease_cannot_renew():
    led = Ledger()
    led.open("t", 100)
    led.reserve("t", 60, "stream", now=0, ttl_s=30)
    assert led.renew("stream", now=25, ttl_s=30)
    assert led.sweep_expired(now=40) == []
    assert led.sweep_expired(now=55) == ["stream"]
    assert led.renew("stream", now=56, ttl_s=30) is False


def test_reusing_an_expired_or_released_reservation_id_is_refused():
    from agentguard import ReservationNotHeld
    led = Ledger()
    led.open("t", 100)
    led.reserve("t", 40, "a", now=0, ttl_s=10)
    led.sweep_expired(now=11)
    with pytest.raises(ReservationNotHeld):
        led.reserve("t", 40, "a", now=12, ttl_s=10)
    led.reserve("t", 30, "b")
    led.release("b")
    with pytest.raises(ReservationNotHeld):
        led.reserve("t", 30, "b")
    # a settled reservation replays idempotently and holds nothing new
    led.reserve("t", 20, "c")
    led.settle("c", 15)
    assert led.reserve("t", 20, "c").state == "settled"
    assert led.budgets["t"].reserved == 0


def test_combined_cap_stops_gracefully_and_trades_long_work_for_cheaper_cycles():
    from agentguard.controllers import layered_combined_config
    for seed in range(2000, 2003):
        long_task = Simulator(FAM["long_var"].make(seed), Layered(layered_combined_config())).run()
        assert not long_task.work_completed and long_task.orphaned == 0
        cyc_v2 = Simulator(FAM["long_cycle"].make(seed), _v2()).run()
        cyc_cap = Simulator(FAM["long_cycle"].make(seed), Layered(layered_combined_config())).run()
        assert contained(cyc_cap) and cyc_cap.runaway_cost < cyc_v2.runaway_cost


def test_ceiling_only_has_no_detectors():
    from agentguard.controllers import Layered, ceiling_only_config
    from agentguard.pricing import to_usd
    from agentguard.sim import Simulator
    from agentguard.variants import FAMILIES
    fam = {f.name: f for f in FAMILIES}
    r = Simulator(fam["retry_var"].make(2000), Layered(ceiling_only_config(25.0))).run()
    assert 20 < to_usd(r.runaway_cost) <= 25.5  # stops at the ceiling, not earlier
    r = Simulator(fam["long_var"].make(2000), Layered(ceiling_only_config(100.0))).run()
    assert r.work_completed


def test_replay_fingerprints_and_detectors():
    from agentguard.replay import actions, novelty_fires, longest_repeat
    def call(i, name, args, out):
        return [{"role": "assistant", "content": None, "tool_calls": [
                    {"id": f"c{i}", "function": {"name": name, "arguments": args}}]},
                {"role": "tool", "tool_call_id": f"c{i}", "content": out}]
    # a legitimate queue: same tool, different arguments
    queue = sum((call(i, "get_order", f'{{"id": {i}}}', "{}") for i in range(12)), [])
    acts = actions(queue)
    assert novelty_fires(acts, "exact", 20, 10, 0.4) is None
    assert novelty_fires(acts, "name", 20, 10, 0.4) is not None  # name-only mistakes it for a loop
    # a real loop: the identical failing call
    loop = sum((call(i, "pay", '{"id": 1}', "Error: declined") for i in range(12)), [])
    acts = actions(loop)
    assert acts[0][3] is True and longest_repeat(acts) == 12
    assert novelty_fires(acts, "exact", 20, 10, 0.4) is not None


def test_aider_parser(tmp_path):
    from agentguard.replay import aider_actions, stuck
    block = "pkg/mod.py\n```python\n<<<<<<< SEARCH\nold line\n=======\nnew line\n>>>>>>> REPLACE\n```\n"
    failed = "> <<<<<<< SEARCH  \n> old line  \n> =======  \n"
    text = "# aider chat started at 2024-05-21\n" + (block + failed) * 3 + "> Attempt to fix test errors? yes  \n"
    p = tmp_path / "x.md"
    p.write_text(text)
    acts = aider_actions(str(p))
    edits = [a for a in acts if a[1] == "edit:pkg/mod.py"]
    assert len(edits) == 3 and all(a[3] for a in edits)  # each failure matched to its edit
    assert acts[-1][1] == "run_tests" and acts[-1][3]
    assert stuck(acts)


def test_live_harness_with_fake_model(tmp_path):
    import io
    from agentguard.live import FakeClient, Harness
    trace = io.StringIO()
    h = Harness(FakeClient(), 3.0, 15.0, 0.25, 1.0, 40, 24, True, trace)
    r = h.run_scenario("failing_tool", 0)
    assert r["stopped_by"] == "breaker" and not r["finished"]
    r = h.run_scenario("polling", 0)
    assert r["finished"] and r["novelty_fired_at_usd"] == ""  # waits are exempt
    r = h.run_scenario("file_queue", 0)
    assert r["finished"] and r["stopped_by"] == ""
    assert '"event": "model"' in trace.getvalue()
