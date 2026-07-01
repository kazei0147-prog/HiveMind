"""2000-round long-term validation with adjusted parameters."""
import sys, json, pathlib, logging
logging.disable(logging.WARNING)
sys.path.insert(0, pathlib.Path(__file__).resolve().parent.as_posix())

from hivemind.config import HiveMindConfig
from hivemind.mother import MotherModule
import visualize as viz

config = HiveMindConfig(
    max_rounds=2000,
    target_value=50.0,
    observation_noise=15.0,
    adoption_reward=6.0,
    inference_cost=5.0,
    confidence_decay_rate=0.05,
    energy_floor=10.0,
    log_level='ERROR',
)

mother = MotherModule(config)
logs = mother.run_simulation()
summary = mother.final_summary()

# Save
out = pathlib.Path(__file__).resolve().parent / "output_2000"
out.mkdir(parents=True, exist_ok=True)
with open(out / "round_logs.json", "w", encoding="utf-8") as f:
    json.dump(logs, f, indent=2, ensure_ascii=False)
with open(out / "summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2, ensure_ascii=False)

# Generate charts
viz.plot_energy_curves(logs, summary, str(out))

print("=" * 60)
print("HiveMind 2000-Round Long-Term Validation")
print("Config: noise=15, reward=6, cost=5, decay=0.05, floor=10")
print("=" * 60)
print(f"Final consensus:  {summary['final_consensus']:.4f}")
print(f"Final error:      {summary['final_error']:.4f}")
print(f"Fallbacks total:  {summary['fallback_count']}")
print(f"Dreams total:     {summary['dream_count']}")
print(f"Deaths total:     {summary['death_count']}")
print(f"Alive at end:     {summary['alive_modules']}")
for mid, ms in summary['module_summaries'].items():
    print(f"  [{mid}] alive={ms['alive']}, bal={ms['wallet']['balance']:.1f}, "
          f"earned={ms['wallet']['total_earned']:.1f}, spent={ms['wallet']['total_spent']:.1f}, "
          f"adopted={ms['adoption_count']}, avg={ms['avg_proposal']}")
print("=" * 60)
