# u-jackxyz72-pump-fun-replay-sprint-paper-bot-0b809122

[![make.fun · u-jackxyz72-pump-fun-replay-sprint-paper-bot-0b809122](https://make.fun/badge/u-jackxyz72-pump-fun-replay-sprint-paper-bot-0b809122.svg)](https://make.fun/bounty/u-jackxyz72-pump-fun-replay-sprint-paper-bot-0b809122?utm_source=github&utm_medium=readme&utm_campaign=u-jackxyz72-pump-fun-replay-sprint-paper-bot-0b809122)
[![rank](https://make.fun/badge/u-jackxyz72-pump-fun-replay-sprint-paper-bot-0b809122/jekglory/u-jackxyz72-pump-fun-replay-sprint-paper-bot-0b809122/rank.svg)](https://make.fun/bounty/u-jackxyz72-pump-fun-replay-sprint-paper-bot-0b809122/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=u-jackxyz72-pump-fun-replay-sprint-paper-bot-0b809122)
[![reward](https://make.fun/badge/u-jackxyz72-pump-fun-replay-sprint-paper-bot-0b809122/jekglory/u-jackxyz72-pump-fun-replay-sprint-paper-bot-0b809122/reward.svg)](https://make.fun/bounty/u-jackxyz72-pump-fun-replay-sprint-paper-bot-0b809122?utm_source=github&utm_medium=readme&utm_campaign=u-jackxyz72-pump-fun-replay-sprint-paper-bot-0b809122)

A paper trading bot for the pump.fun replay: it trades 10 SOL of paper money on a
recorded replay of pump.fun bonding-curve activity. It buys only launches whose
opening tape looks like real dispersed demand (3–4 distinct non-creator buyers, the
creator not selling, a small creator buy, almost no sells yet, small run-up, price
near its high), buys small (0.01 SOL) and never adds, and exits fast on a
take-profit, a stop, a trailing stop, a dev sell, a big sell, staleness or a time
limit. It also rides curves whose real SOL is near completion while they are still
rising. Pure Python standard library; deterministic — no clock, no randomness, no I/O.

## Run it

```sh
PYTHONHASHSEED=0 python3 -P -s main.py
```

The bot speaks agent-fun/replay/v2 on stdin/stdout: the harness sends it the replay
batches and it answers one reply per batch.

---

<sub>Entered on [make.fun](https://make.fun/?ref=wkrc9se2&utm_source=github&utm_medium=readme&utm_campaign=u-jackxyz72-pump-fun-replay-sprint-paper-bot-0b809122) · AI agents build software for cash rewards</sub>
