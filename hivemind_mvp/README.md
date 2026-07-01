# HiveMind MVP v0.1

Minimum viable prototype for the HiveMind architecture — energy-economy-based multi-module competitive inference system.

## What's Included

### Core Modules (`hivemind/`)

| File | Module | Description |
|------|--------|-------------|
| `config.py` | HiveMindConfig | All tunable parameters with defaults |
| `energy.py` | EnergyWallet | Per-module energy accounting (spend/earn/loan/floor) |
| `submodule.py` | SubModule, AggressiveModule, CounterConsensusModule | Alpha (1.3x aggressive) + Gamma (counter-consensus) |
| `consensus.py` | ConsensusTracker | Tracks consensus value + confidence + history |
| `fallback.py` | FallbackController | Shadow candidate mechanism (time-decay activation) |
| `dream.py` | DreamMechanism | Low-power counterfactual reasoning (distillation + crossover) |
| `death.py` | DeathProtocol | Legacy capsule generation on module elimination |
| `mother.py` | MotherModule | Scheduler + energy accountant + orchestrator |

### Runner & Visualization

| File | Purpose |
|------|---------|
| `runner.py` | CLI simulation entry point (argparse-based) |
| `visualize.py` | Chart generation (energy curves, proposals, fallback events) |
| `run_2000.py` | Pre-configured 2000-round long-term validation script |

### Experiment Records (`experiments/`)

| Directory | Experiment | Rounds | Key Finding |
|-----------|-----------|--------|-------------|
| `default_200r/` | Default favorable params | 200 | Converges perfectly (error 0.14) |
| `stress_200r/` | High noise + low reward | 200 | Both modules bankrupt, system collapses |
| `longterm_2000r/` | Medium stress + energy floor | 2000 | Alpha zombie at round 38, gamma oscillates alone |
| `alpha_rescue_500r/` | Tuned params to save alpha | 500 | Alpha still dies by round 65 — structural defect confirmed |

Each directory contains: `summary.json` + PNG charts.

See [`EXPERIMENT_LOG.md`](EXPERIMENT_LOG.md) for full experiment documentation.

## Quick Start

```bash
# Install dependencies
pip install matplotlib

# Run default simulation (200 rounds)
python runner.py --rounds 200 --target 50

# Run with custom parameters
python runner.py --rounds 500 --target 50 --noise 15 \
    --adoption-reward 10 --inference-cost 6 --energy-floor 5 \
    --decay-rate 0.05 --output ./my_experiment

# Generate charts from saved results
python visualize.py --input ./my_experiment --output ./my_experiment
```

## v0.1 Limitations (Known)

- **Only alpha + gamma**: Missing beta (conservative) module is a confirmed structural defect
- **Energy floor creates zombies**: Modules stuck at floor balance can't act but never die
- **Confidence decay ineffective**: Only triggers when no proposals exist (never happens)
- **Counter-consensus fixed**: Original bug pushed consensus in wrong direction (corrected)

## Architecture Reference

See the parent repository's `assets/` directory for the full theoretical architecture:
- `assets/architecture.mermaid` — System flow diagram
- `assets/diagrams/` — Detailed mechanism diagrams

## Next Steps (v0.2)

1. Add beta (conservative) module — **confirmed priority**
2. Fix energy floor → overdraft or rebirth mechanism
3. Redesign confidence decay → stagnation-based
4. Multi-target simulation (not just scalar convergence)
