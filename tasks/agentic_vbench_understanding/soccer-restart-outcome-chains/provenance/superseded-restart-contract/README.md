# The superseded restart contract

This task first asked for every visible ball restart as `(t, restart_type, team, outcome)`,
scored by an order-preserving F1 with a 3 s tolerance. That contract was replaced by the
action ledger in `steps/solve/`. An in-image Codex run scored 0.3529 against the family's
0.10 ceiling, almost all of it on throw-ins, and the prompt turned out to give direct and
indirect free kicks their laws-of-the-game meaning where SoccerNet's labels mean shot
intent. `calibration/scores.md` tells that story in full.

What is kept here, so every number from that contract can still be regraded:

| file | what it is |
|---|---|
| `instruction.md` | the prompt those runs were given. Its SHA256 equals the `prompt_sha256` every superseded manifest records. |
| `judge.py` | the scorer and the 72-restart key those runs were graded by. Regrading their shipped solutions with it reproduces each `reward.json`. |
| `ablations/measured/` | the three degraded-input runs against that prompt |

The runs themselves are in `calibration/rollouts/superseded-restart-contract/`, and
`calibration/verify_scores.py` regrades all of them with this scorer.
