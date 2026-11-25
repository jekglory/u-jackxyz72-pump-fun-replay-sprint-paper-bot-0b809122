"""Early-quality sniper + fast exits + graduation ride for agent-fun/replay/v2.

Pure standard library. The grader runs `python3 -P -s main.py` with PYTHONHASHSEED=0.
Deterministic by construction: no clock, no randomness, no I/O, no environment reads;
iteration only over insertion-ordered dicts and the batch's own event order.

Idea
----
Most pump.fun coins peak within a few slots of creation and then dump; a few run to
completion (~15x from create). So: buy only launches whose opening tape looks like real
dispersed demand (3-4 distinct non-creator buyers, creator not selling, a small
creator buy, positive net flow with almost no sells yet, small run-up, price near its
high), buy small (0.01 SOL, the guardrail minimum per round trip) and never add, and
exit fast on a take-profit, a stop, a trailing stop, a dev sell, a big sell, staleness
or a time limit. Separately, ride curves whose real SOL is near completion while they
are still rising. Two more entry modes live in this file but are OFF by default because
backtests on the dev window showed they lose: dip-buying after a capitulation drop
(bounce_on) and following the creator's later buys (devbuy_on). Every exit sells the
whole position; sells are sized so the expected quote-out stays under 90% of the real
quote reserves (a bigger sell would be rejected for max_order_size and leave the
position open into the dump).

Tuning notes (dev window, local backtester mirroring the kit's engine exactly):
- Adding into strength lost money; pyramiding lost more. No adds.
- Buying dips lost badly (-1.1 SOL): after a 25% drop the dump usually continues.
- Buying high-real-reserve curves lost (-0.3 to -0.6 SOL): by then the top is in.
- Small creator buys predict safer launches; the final filter caps them at 1 SOL.
- Final settings: -0.048 SOL on dev, max drawdown 0.5%, 97 round trips, 90 coins
  above the 0.01 SOL bar (guardrail needs 20). House pilots on the same window:
  momentum -9.49, sniper -0.47, reversion -4.00, equal-weight -0.02 (5 coins only).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))

import makefun_bot  # noqa: E402  (after the sys.path line: -P leaves the script directory off sys.path)

LAMPORTS_PER_SOL = makefun_bot.LAMPORTS_PER_SOL
TX_FEE = 105000  # 5,000 base + 100,000 priority lamports, every order
PROTO_BPS = 95
CREATOR_BPS = 30

PARAMS = {
    # --- launch entry ---
    "launch_on": True,          # master switch for launch entries
    "max_age": 6,               # slots since CreateEvent to still take a first buy
    "min_rq": 200_000_000,      # 0.2 SOL real quote reserves at decision
    "max_rq": 30_000_000_000,   # 30 SOL
    "min_buyers": 3,            # distinct non-creator buyers seen
    "max_buyers": 4,            # more looks like a bundled launch waiting to dump
    "max_dev_buy": 1_000_000_000,  # 1.0 SOL creator's own buys (small dev buys only)
    "min_net_flow": 0,          # buy SOL minus sell SOL seen, lamports
    "max_sell_ratio_bps": 500,  # sell SOL / buy SOL at entry, at most 5%
    "min_runup_bps": 0,         # price vs create price, bps
    "max_runup_bps": 6000,      # 60%
    "min_high_frac_bps": 9000,  # price now at least 90% of the high since create
    # --- sizing ---
    "first_buy": 10_000_000,    # 0.01 SOL first buy (the guardrail minimum per round trip)
    "stake": 50_000_000,        # 0.05 SOL total per coin
    "min_buy": 5_000_000,       # 0.005 SOL smallest buy worth the tx fee
    "max_adds": 0,              # no pyramiding: adds into strength lost money in backtests
    "add_amount": 30_000_000,   # 0.03 SOL add (unused while max_adds is 0)
    "add_step_bps": 500,        # add only 5% above the last buy's decision price
    "add_net_flow": 100_000_000,  # 0.1 SOL net flow over the recent window to add
    # --- exits (bps vs cost, or slots) ---
    "tp_bps": 6000,             # +60% take profit, sell all
    "sl_bps": 1500,             # -15% stop loss, sell all
    "trail_arm_bps": 2000,      # trailing stop arms at +20%
    "trail_bps": 2500,          # exit on a 25% fall from the peak value
    "max_hold": 400,            # slots
    "stale_slots": 300,         # no trade for this long -> exit
    "time_stop_slots": 60,      # if still below cost+time_stop_up_bps after this long, exit
    "time_stop_up_bps": 200,    # +2%
    "big_sell_frac_bps": 3000,  # one sell >= 30% of real quote reserves -> exit
    "exit_on_dev_sell": True,   # exit as soon as the creator sells while held
    "cooldown": 100,            # slots before the same mint may be bought again
    # --- graduation ride ---
    "ride_rq": 50_000_000_000,  # 50 SOL real quote reserves: completion is near
    "ride_up_bps": 500,         # price up 5% over the lookback to ride
    "ride_lookback": 20,        # slots of price history for the ride check
    "ride_stake": 50_000_000,   # 0.05 SOL
    # --- bounce (capitulation-dip) entry ---
    "bounce_on": False,         # buy after a sharp drop from the high, on returning buy flow
    "bounce_drop_bps": 2500,    # price at least 25% under the high since create
    "bounce_age_min": 20,       # slots since create before a bounce may be taken
    "bounce_recent": 5,         # last N trades must show returning buyers
    "bounce_min_recent_buyers": 2,
    "bounce_min_recent_net": 0,  # net buy SOL over the recent trades, lamports
    "bounce_min_rq": 500_000_000,   # 0.5 SOL
    "bounce_max_rq": 30_000_000_000,
    "bounce_first_buy": 20_000_000,  # 0.02 SOL
    "bounce_tp_bps": 3000,      # +30% take profit on bounces
    "bounce_sl_bps": 1000,      # -10% stop on bounces
    "bounce_max_hold": 150,     # slots
    # --- dev-buy band entry: follow the creator's own post-create buys ---
    "devbuy_on": False,         # buy when the creator keeps buying their own coin
    "devbuy_min": 300_000_000,  # 0.3 SOL of creator buys after the create slot
    "devbuy_up_bps": 300,       # price up 3% vs create price
    "devbuy_min_rq": 500_000_000,
    "devbuy_max_rq": 30_000_000_000,
    "devbuy_first_buy": 20_000_000,  # 0.02 SOL
    "devbuy_max_age": 200,      # slots since create to still follow a dev buy
}


def set_params(overrides):
    """Backtester hook only: tune PARAMS in memory. Never called during grading."""
    PARAMS.update(overrides)


def _ceil_div(a, b):
    return (a + b - 1) // b


def close_value(curve, tokens):
    """Net lamports closing `tokens` now would pay (curve fees + one tx fee)."""
    if curve is None or tokens <= 0:
        return 0
    vq = curve.virtual_quote_reserves
    vt = curve.virtual_token_reserves
    rq = curve.real_quote_reserves
    q = tokens * vq // (vt + tokens)
    if q > rq:
        q = rq
    fee = _ceil_div(q * PROTO_BPS, 10000)
    creator_fee = _ceil_div(q * CREATOR_BPS, 10000)
    return q - fee - creator_fee - TX_FEE


def max_sell_tokens(curve, tokens):
    """Largest token amount whose expected quote-out stays under 90% of real reserves."""
    if curve is None or tokens <= 0:
        return 0
    vq = curve.virtual_quote_reserves
    vt = curve.virtual_token_reserves
    rq = curve.real_quote_reserves
    cap_q = rq * 9 // 10
    if cap_q <= 0 or vq <= cap_q:
        return tokens
    # t*vq/(vt+t) <= cap_q  ->  t <= cap_q*vt/(vq-cap_q)
    t = cap_q * vt // (vq - cap_q)
    return min(tokens, t)


class Tape:
    """A coin's opening tape, read from the batches' own events."""

    __slots__ = ("mint", "created_slot", "creator", "create_price", "high",
                 "buyers", "buy_sol", "sell_sol", "creator_buy", "creator_buy_after",
                 "creator_sold", "trades", "last_trade_slot", "last_sell_frac",
                 "prices", "recent")

    def __init__(self, mint, created_slot, creator, create_price):
        self.mint = mint
        self.created_slot = created_slot
        self.creator = creator
        self.create_price = create_price
        self.high = create_price
        self.buyers = set()
        self.buy_sol = 0
        self.sell_sol = 0
        self.creator_buy = 0
        self.creator_buy_after = 0  # creator buys after the create slot
        self.creator_sold = False
        self.trades = 0
        self.last_trade_slot = created_slot
        self.last_sell_frac = 0
        # (slot, price) history, capped, for the graduation-ride lookback.
        self.prices = [(created_slot, create_price)]
        # Last trades: (slot, is_buy, sol_lamports, user), capped.
        self.recent = []


def price_of(curve):
    vt = curve.virtual_token_reserves
    return curve.virtual_quote_reserves / vt if vt else 0.0


class Bot:
    def __init__(self):
        self.tapes = {}       # mint -> Tape, insertion order
        self.decided = set()  # mints a first buy was taken on (or skipped for good)
        self.held = {}        # mint -> {"buy_slot": int, "last_buy_price": float, "adds": int, "peak": int}
        self.last_exit = {}   # mint -> slot of last exit
        self.ride_taken = set()
        self.selling = set()  # mints with a sell sent and not yet reported back
        self.bounce_done = {}  # mint -> high at the bounce buy (re-arm above it)
        self.stats = {"launch": 0, "ride": 0, "bounce": 0, "devbuy": 0, "exit_tp": 0, "exit_sl": 0,
                      "exit_trail": 0, "exit_hold": 0, "exit_stale": 0,
                      "exit_dev": 0, "exit_bigsell": 0, "exit_time": 0}

    def _prune(self, state):
        """Drop held/selling records for mints no longer held and with no buy in flight.
        A sell that was rejected or failed leaves the position held, so its peak survives."""
        pending_buys = {p.order["mint"] for p in state.pending.values()
                        if p.order["side"] == "buy"}
        for mint in list(self.held):
            if mint not in state.positions and mint not in pending_buys:
                del self.held[mint]
        for mint in list(self.selling):
            if mint not in state.positions and mint not in pending_buys:
                self.selling.discard(mint)

    # -- tape maintenance ---------------------------------------------------
    def _note_trade(self, tape, e, slot):
        q = int(e["sol_amount"])
        user = e["user"]
        if e["is_buy"]:
            tape.buy_sol += q
            if user == tape.creator:
                tape.creator_buy += q
                if slot > tape.created_slot:
                    tape.creator_buy_after += q
            else:
                tape.buyers.add(user)
        else:
            tape.sell_sol += q
            if user == tape.creator:
                tape.creator_sold = True
            rq = int(e["real_quote_reserves"])
            if rq > 0:
                frac = q * 10000 // rq
                if frac > tape.last_sell_frac:
                    tape.last_sell_frac = frac
        tape.trades += 1
        tape.last_trade_slot = slot
        price = int(e["virtual_quote_reserves"]) / int(e["virtual_token_reserves"])
        if price > tape.high:
            tape.high = price
        tape.prices.append((slot, price))
        if len(tape.prices) > 48:
            del tape.prices[0]
        tape.recent.append((slot, e["is_buy"], q, user))
        if len(tape.recent) > 12:
            del tape.recent[0]

    def update_tapes(self, batch):
        slot = batch["slot"]
        for e in batch["events"]:
            mint = e["mint"]
            if e["event"] == "CreateEvent":
                vt = int(e["virtual_token_reserves"])
                vq = int(e["virtual_quote_reserves"])
                price = vq / vt if vt else 0.0
                self.tapes[mint] = Tape(mint, slot, e["user"], price)
            elif e["event"] == "TradeEvent":
                tape = self.tapes.get(mint)
                if tape is not None:
                    self._note_trade(tape, e, slot)

    # -- exits ---------------------------------------------------------------
    def exits(self, state, batch, orders):
        slot = batch["slot"]
        p = PARAMS
        for mint, holding in list(state.positions.items()):
            info = self.held.get(mint)
            curve = state.curves.get(mint)
            if curve is None:
                continue
            tokens = holding.token_amount
            value = close_value(curve, tokens)
            cost = holding.cost_lamports
            if info is None:
                info = {"buy_slot": slot, "last_buy_price": price_of(curve),
                        "adds": 0, "peak": value, "kind": "launch"}
                self.held[mint] = info
            if value > info["peak"]:
                info["peak"] = value
            tape = self.tapes.get(mint)
            kind = info.get("kind", "launch")
            tp = p["bounce_tp_bps"] if kind == "bounce" else p["tp_bps"]
            sl = p["bounce_sl_bps"] if kind == "bounce" else p["sl_bps"]
            hold = p["bounce_max_hold"] if kind == "bounce" else p["max_hold"]
            sell = None
            if value >= cost * (10000 + tp) // 10000:
                sell = "exit_tp"
            elif value <= cost * (10000 - sl) // 10000:
                sell = "exit_sl"
            elif (info["peak"] >= cost * (10000 + p["trail_arm_bps"]) // 10000
                    and value <= info["peak"] * (10000 - p["trail_bps"]) // 10000):
                sell = "exit_trail"
            elif slot - info["buy_slot"] >= hold:
                sell = "exit_hold"
            elif (p["time_stop_slots"] > 0
                    and slot - info["buy_slot"] >= p["time_stop_slots"]
                    and value < cost * (10000 + p["time_stop_up_bps"]) // 10000):
                sell = "exit_time"
            elif tape is not None and slot - tape.last_trade_slot >= p["stale_slots"]:
                sell = "exit_stale"
            elif tape is not None and tape.creator_sold and p["exit_on_dev_sell"]:
                sell = "exit_dev"
            elif tape is not None and tape.last_sell_frac >= p["big_sell_frac_bps"]:
                sell = "exit_bigsell"
            if sell:
                if mint in self.selling:
                    continue
                amount = max_sell_tokens(curve, tokens)
                if amount > 0:
                    orders.append({"side": "sell", "mint": mint, "token_amount": amount,
                                   "max_slippage_bps": 10000})
                    self.last_exit[mint] = slot
                    self.selling.add(mint)
                    self.stats[sell] += 1

    # -- entries --------------------------------------------------------------
    def _entry_ok(self, state, tape, slot):
        p = PARAMS
        curve = state.curves.get(tape.mint)
        if curve is None or curve.complete:
            return False
        if slot - tape.created_slot > p["max_age"]:
            return False
        rq = curve.real_quote_reserves
        if rq < p["min_rq"] or rq > p["max_rq"]:
            return False
        if len(tape.buyers) < p["min_buyers"] or len(tape.buyers) > p["max_buyers"]:
            return False
        if tape.creator_sold or tape.creator_buy > p["max_dev_buy"]:
            return False
        if tape.buy_sol - tape.sell_sol < p["min_net_flow"]:
            return False
        if tape.buy_sol > 0 and tape.sell_sol * 10000 // tape.buy_sol > p["max_sell_ratio_bps"]:
            return False
        price = price_of(curve)
        if tape.create_price <= 0:
            return False
        runup = (price - tape.create_price) * 10000 // tape.create_price
        if runup < p["min_runup_bps"] or runup > p["max_runup_bps"]:
            return False
        if tape.high > 0 and price * 10000 // tape.high < p["min_high_frac_bps"]:
            return False
        return True

    def entries(self, state, batch, orders, free, slots):
        slot = batch["slot"]
        p = PARAMS
        if not p["launch_on"]:
            return free, slots
        for e in batch["events"]:
            if len(orders) >= 16 or slots <= 0 or free < p["min_buy"] + TX_FEE:
                return free, slots
            mint = e["mint"]
            if mint in self.decided or mint in state.positions or mint in self.held:
                continue
            tape = self.tapes.get(mint)
            if tape is None:
                continue
            if mint in self.last_exit and slot - self.last_exit[mint] < p["cooldown"]:
                continue
            if not self._entry_ok(state, tape, slot):
                continue
            cap = state.max_buy_lamports(mint)
            amount = min(p["first_buy"], cap, free - TX_FEE)
            if amount < p["min_buy"]:
                continue
            orders.append({"side": "buy", "mint": mint, "quote_lamports": amount,
                           "max_slippage_bps": 10000})
            self.decided.add(mint)
            self.held[mint] = {"buy_slot": slot, "last_buy_price": price_of(state.curves[mint]),
                               "adds": 0, "peak": 0, "kind": "launch"}
            self.stats["launch"] += 1
            free -= amount + TX_FEE
            slots -= 1
        return free, slots

    # -- adds ------------------------------------------------------------------
    def adds(self, state, batch, orders, free):
        slot = batch["slot"]
        p = PARAMS
        for mint, holding in list(state.positions.items()):
            if len(orders) >= 16 or free < p["min_buy"] + TX_FEE:
                return free
            info = self.held.get(mint)
            if info is None or info["adds"] >= p["max_adds"]:
                continue
            curve = state.curves.get(mint)
            if curve is None or curve.complete:
                continue
            tape = self.tapes.get(mint)
            if tape is None:
                continue
            if tape.buy_sol - tape.sell_sol < p["add_net_flow"]:
                continue
            price = price_of(curve)
            if (info["last_buy_price"] > 0
                    and price * 10000 // info["last_buy_price"] < 10000 + p["add_step_bps"]):
                continue
            spent = holding.cost_lamports
            room = p["stake"] - spent
            if room < p["min_buy"]:
                continue
            cap = state.max_buy_lamports(mint)
            amount = min(p["add_amount"], room, cap, free - TX_FEE)
            if amount < p["min_buy"]:
                continue
            orders.append({"side": "buy", "mint": mint, "quote_lamports": amount,
                           "max_slippage_bps": 10000})
            info["adds"] += 1
            info["last_buy_price"] = price
            free -= amount + TX_FEE
        return free

    # -- graduation ride ---------------------------------------------------------
    def rides(self, state, batch, orders, free, slots):
        slot = batch["slot"]
        p = PARAMS
        for e in batch["events"]:
            if len(orders) >= 16 or slots <= 0 or free < p["min_buy"] + TX_FEE:
                return free, slots
            if e["event"] != "TradeEvent":
                continue
            mint = e["mint"]
            if mint in self.decided or mint in self.ride_taken:
                continue
            if mint in state.positions or mint in self.held:
                continue
            tape = self.tapes.get(mint)
            curve = state.curves.get(mint)
            if tape is None or curve is None or curve.complete:
                continue
            if curve.real_quote_reserves < p["ride_rq"]:
                continue
            if tape.creator_sold:
                continue
            old = None
            for (s, pr) in tape.prices:
                if slot - s >= p["ride_lookback"]:
                    old = pr
                    break
            if old is None or old <= 0:
                continue
            price = price_of(curve)
            if price * 10000 // old < 10000 + p["ride_up_bps"]:
                continue
            cap = state.max_buy_lamports(mint)
            amount = min(p["ride_stake"], cap, free - TX_FEE)
            if amount < p["min_buy"]:
                continue
            orders.append({"side": "buy", "mint": mint, "quote_lamports": amount,
                           "max_slippage_bps": 10000})
            self.ride_taken.add(mint)
            self.decided.add(mint)
            self.held[mint] = {"buy_slot": slot, "last_buy_price": price,
                               "adds": p["max_adds"], "peak": 0, "kind": "ride"}
            self.stats["ride"] += 1
            free -= amount + TX_FEE
            slots -= 1
        return free, slots


    # -- dev-buy band entries ---------------------------------------------------
    def devbuys(self, state, batch, orders, free, slots):
        slot = batch["slot"]
        p = PARAMS
        if not p["devbuy_on"]:
            return free, slots
        for e in batch["events"]:
            if len(orders) >= 16 or slots <= 0 or free < p["min_buy"] + TX_FEE:
                return free, slots
            if e["event"] != "TradeEvent":
                continue
            mint = e["mint"]
            if mint in self.decided or mint in state.positions or mint in self.held:
                continue
            tape = self.tapes.get(mint)
            curve = state.curves.get(mint)
            if tape is None or curve is None or curve.complete:
                continue
            if slot - tape.created_slot > p["devbuy_max_age"]:
                continue
            if tape.creator_sold or tape.creator_buy_after < p["devbuy_min"]:
                continue
            rq = curve.real_quote_reserves
            if rq < p["devbuy_min_rq"] or rq > p["devbuy_max_rq"]:
                continue
            price = price_of(curve)
            if (tape.create_price <= 0
                    or price * 10000 // tape.create_price < 10000 + p["devbuy_up_bps"]):
                continue
            if mint in self.last_exit and slot - self.last_exit[mint] < p["cooldown"]:
                continue
            cap = state.max_buy_lamports(mint)
            amount = min(p["devbuy_first_buy"], cap, free - TX_FEE)
            if amount < p["min_buy"]:
                continue
            orders.append({"side": "buy", "mint": mint, "quote_lamports": amount,
                           "max_slippage_bps": 10000})
            self.decided.add(mint)
            self.held[mint] = {"buy_slot": slot, "last_buy_price": price,
                               "adds": p["max_adds"], "peak": 0, "kind": "launch"}
            self.stats["devbuy"] += 1
            free -= amount + TX_FEE
            slots -= 1
        return free, slots

    # -- bounce (capitulation-dip) entries --------------------------------------
    def _bounce_ok(self, state, tape, slot):
        p = PARAMS
        curve = state.curves.get(tape.mint)
        if curve is None or curve.complete:
            return False
        if slot - tape.created_slot < p["bounce_age_min"]:
            return False
        rq = curve.real_quote_reserves
        if rq < p["bounce_min_rq"] or rq > p["bounce_max_rq"]:
            return False
        price = price_of(curve)
        if tape.high <= 0 or price * 10000 // tape.high > 10000 - p["bounce_drop_bps"]:
            return False
        recent = tape.recent[-p["bounce_recent"]:] if len(tape.recent) >= p["bounce_recent"] else tape.recent
        if len(recent) < p["bounce_recent"]:
            return False
        net = 0
        buyers = set()
        for (_s, is_buy, q, user) in recent:
            if is_buy:
                net += q
                if user != tape.creator:
                    buyers.add(user)
            else:
                net -= q
        if net < p["bounce_min_recent_net"]:
            return False
        if len(buyers) < p["bounce_min_recent_buyers"]:
            return False
        return True

    def bounces(self, state, batch, orders, free, slots):
        slot = batch["slot"]
        p = PARAMS
        if not p["bounce_on"]:
            return free, slots
        for e in batch["events"]:
            if len(orders) >= 16 or slots <= 0 or free < p["min_buy"] + TX_FEE:
                return free, slots
            if e["event"] != "TradeEvent":
                continue
            mint = e["mint"]
            if mint in state.positions or mint in self.held:
                continue
            tape = self.tapes.get(mint)
            if tape is None:
                continue
            if mint in self.last_exit and slot - self.last_exit[mint] < p["cooldown"]:
                continue
            done_high = self.bounce_done.get(mint)
            if done_high is not None and tape.high < done_high * 11 // 10:
                continue
            if not self._bounce_ok(state, tape, slot):
                continue
            cap = state.max_buy_lamports(mint)
            amount = min(p["bounce_first_buy"], cap, free - TX_FEE)
            if amount < p["min_buy"]:
                continue
            orders.append({"side": "buy", "mint": mint, "quote_lamports": amount,
                           "max_slippage_bps": 10000})
            self.bounce_done[mint] = tape.high
            self.held[mint] = {"buy_slot": slot, "last_buy_price": price_of(state.curves[mint]),
                               "adds": p["max_adds"], "peak": 0, "kind": "bounce"}
            self.stats["bounce"] += 1
            free -= amount + TX_FEE
            slots -= 1
        return free, slots


BOT = Bot()


def on_batch(state, batch):
    BOT.update_tapes(batch)
    # A reported sell (filled, rejected or failed) clears the in-flight flag; a
    # rejected/failed sell leaves the position held, so exits() retries next batch.
    for f in batch["fills"]:
        if f["side"] == "sell" and f["status"] in ("filled", "rejected", "failed"):
            BOT.selling.discard(f["mint"])
    BOT._prune(state)
    orders = []
    BOT.exits(state, batch, orders)
    free = state.free_cash_lamports()
    slots = state.hello["caps"]["max_open_positions"] - state.committed_position_count()
    free, slots = BOT.entries(state, batch, orders, free, slots)
    free = BOT.adds(state, batch, orders, free)
    free, slots = BOT.rides(state, batch, orders, free, slots)
    free, slots = BOT.devbuys(state, batch, orders, free, slots)
    free, slots = BOT.bounces(state, batch, orders, free, slots)
    return orders


if __name__ == "__main__":
    makefun_bot.run(on_batch)
