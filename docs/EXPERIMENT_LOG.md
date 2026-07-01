# HiveMind v0.1 Experiment Log

**Date**: 2026-07-01  
**MVP Version**: v0.1 (alpha + gamma only, no beta)  
**Researcher**: kazei0147-prog + AI collaboration  

---

## Experiment 1: Default Parameters (200 rounds)

**Purpose**: Verify basic mechanism functionality under favorable conditions.

| Parameter | Value |
|-----------|-------|
| Rounds | 200 |
| Target | 50 |
| Noise | 10 |
| Adoption Reward | 15 |
| Inference Cost | 5 |
| Confidence Decay | 0.02 |
| Energy Floor | None (original) |

**Key Results**:
- Final consensus: **50.14** (error = 0.14)
- Alpha survived all 200 rounds (net reward +10 per adoption)
- Gamma survived all 200 rounds
- Fallback triggered: **0 times** (confidence stayed at 1.0)
- Dream triggered: **0 times**
- Death triggered: **0 times**

**Observations**:
- System converges beautifully when reward >> cost (15 vs 5)
- Both modules accumulate energy indefinitely ("self-fattening")
- Confidence never decays because modules always propose → mechanism never tested
- Counter-consensus bug discovered and fixed (see code history)

**Files**: `experiments/default_200r/`

---

## Experiment 2: Stress Test (200 rounds)

**Purpose**: Push system to the brink — high noise, low reward, high cost.

| Parameter | Value |
|-----------|-------|
| Rounds | 200 |
| Target | 50 |
| Noise | 30 |
| Adoption Reward | 5 |
| Inference Cost | 8 |
| Confidence Decay | 0.02 |
| Energy Floor | None |

**Key Results**:
- Alpha went bankrupt within ~20 rounds
- Gamma went bankrupt shortly after
- Fallback triggered: **142 times** (high noise caused constant consensus swings)
- Dream triggered: **1 time**
- System entered "single-point oscillation" after modules died

**Observations**:
- When reward < cost, modules cannot sustain themselves
- Fallback mechanism activates but can't rescue (only reuses old consensus)
- Without live modules, system degrades to noise-driven oscillation
- **Critical finding**: two-module architecture is fragile under stress

**Files**: `experiments/stress_200r/`

---

## Experiment 3: Long-Term Validation (2000 rounds)

**Purpose**: Test whether system can self-sustain over extended iteration.

| Parameter | Value |
|-----------|-------|
| Rounds | 2000 |
| Target | 50 |
| Noise | 15 |
| Adoption Reward | 6 |
| Inference Cost | 5 |
| Confidence Decay | 0.05 |
| Energy Floor | 10 |

**Key Results**:

| Checkpoint | Consensus | Error | Alpha Status | Fallbacks |
|-------------|-----------|-------|--------------|-----------|
| 500 | 35.52 | 14.48 | Zombie (bal=10) | 0 |
| 1000 | 53.10 | 3.10 | Zombie | 0 |
| 1500 | 38.60 | 11.40 | Zombie | 0 |
| 2000 | 53.35 | 3.35 | Zombie | 0 |

- Alpha became zombie at **round 38** (balance = floor = 10, can't afford cost 5 + floor 10)
- Alpha adopted **0 times** out of 2000 rounds
- Gamma adopted **2000 times** (every round, no competition)
- Fallback triggered: **0 times** (confidence never decayed below threshold)

**Observations**:
- `energy_floor=10` creates "zombie modules" — alive but unable to act
- Gamma's counter-consensus oscillates without an opponent (35→53→38→53)
- Confidence decay mechanism is ineffective: it only decays when NO proposals exist
- **Structural conclusion**: Without a conservative (beta) module, the system cannot self-sustain

**Files**: `experiments/longterm_2000r/`

---

## Experiment 4: Alpha Rescue Attempt (500 rounds)

**Purpose**: Test whether parameter tuning alone can save alpha from bankruptcy.

| Parameter | Value | Change |
|-----------|-------|--------|
| Rounds | 500 | - |
| Target | 50 | - |
| Noise | 15 | ↓ from 30 |
| Adoption Reward | 10 | ↑ from 5 (net +4 vs +2) |
| Inference Cost | 6 | ↓ from 8 |
| Confidence Decay | 0.05 | ↑ from 0.02 |
| Energy Floor | 5 | ↓ from 10 |

**Key Results**:

| Checkpoint | Consensus | Error | Alpha Balance | Alpha Adopted |
|-------------|-----------|-------|---------------|---------------|
| 50 | 65.74 | 15.74 | 9.0 | 0 |
| 100 | 52.29 | 2.29 | 5.0 (zombie) | 0 |
| 200 | 52.31 | 2.31 | 5.0 | 0 |
| 500 | 55.63 | 5.63 | 5.0 | 0 |

- Alpha survived from round 38 → **round 65** (27 rounds longer than before)
- But still became zombie before round 100
- Alpha adopted **0 times** even with higher reward (its 1.3x bias keeps proposals too high)
- Gamma still dominates all adoptions

**Conclusion**: **Parameter tuning cannot rescue alpha.** The structural deficiency is confirmed:
- Alpha's aggressive bias (1.3x) makes its proposals consistently overshoot
- Without a conservative anchor, the system oscillates
- **Beta (conservative) module is a structural necessity, not an optional enhancement**

**Files**: `experiments/alpha_rescue_500r/`

---

## Summary of v0.1 Findings

### Confirmed
1. **Missing beta is a structural defect** — parameter tuning alone cannot stabilize the system
2. **Energy floor creates zombies** — alive but unable to act is worse than genuinely dead
3. **Confidence decay is ineffective** — it only triggers when no proposals exist, which never happens
4. **Counter-consensus needs an opponent** — without alpha, gamma oscillates against itself

### Bugs Fixed
1. Counter-consensus direction bug: gamma was pushing consensus *higher* when it was already high (fixed to pull toward observation)

### Next Steps (v0.2)
1. Add beta (conservative) module — this is the confirmed priority
2. Fix energy floor: either allow temporary overdraft with interest, or remove floor and add rebirth mechanism
3. Redesign confidence decay: should decay based on *stagnation* not just proposal absence
4. Run 2000+ round test with all three modules

---

> These experiments were conducted using the HiveMind v0.1 MVP prototype.  
> All charts and raw data are included in the `experiments/` subdirectories.
