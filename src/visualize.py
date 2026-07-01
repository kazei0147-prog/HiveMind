"""
HiveMind MVP Visualization

Energy curves, consensus convergence, fallback events, and proposal scatter plots.
"""

import json
import sys
from pathlib import Path

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


def load_results(output_dir: str = "./output") -> tuple:
    """Load simulation results"""
    output_path = Path(output_dir)
    with open(output_path / "round_logs.json", "r", encoding="utf-8") as f:
        logs = json.load(f)
    with open(output_path / "summary.json", "r", encoding="utf-8") as f:
        summary = json.load(f)
    return logs, summary


def plot_energy_curves(logs: list, summary: dict, output_dir: str = "./output"):
    """Generate all visualization charts"""
    if not HAS_MATPLOTLIB:
        print("matplotlib not installed. Install: pip install matplotlib")
        return

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    rounds = [l["round"] for l in logs]
    module_ids = list(summary["module_summaries"].keys())

    # ── Main 2x2 chart ──
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("HiveMind MVP - Energy Economics & Consensus Evolution", fontsize=16, fontweight='bold')

    # Energy balance
    ax = axes[0, 0]
    for mid in module_ids:
        balances = [l["module_states"].get(mid, {}).get("energy_balance", 0) for l in logs]
        ax.plot(rounds, balances, label=mid, linewidth=1.5)
    ax.set_xlabel("Round")
    ax.set_ylabel("Energy Balance")
    ax.set_title("Module Energy Balance Over Time")
    ax.legend()
    ax.grid(True, alpha=0.3)

    # Consensus convergence
    ax = axes[0, 1]
    consensus_values = [l.get("consensus_value", 0) for l in logs]
    target = summary["target_value"]
    ax.plot(rounds, consensus_values, label="Consensus", color="#2196F3", linewidth=1.5)
    ax.axhline(y=target, color="#F44336", linestyle="--", label=f"Target ({target})", linewidth=1.5)
    ax.set_xlabel("Round")
    ax.set_ylabel("Consensus Value")
    ax.set_title("Consensus Convergence")
    ax.legend()
    ax.grid(True, alpha=0.3)

    # Confidence
    ax = axes[1, 0]
    confidences = [l.get("consensus_confidence", 0) for l in logs]
    ax.plot(rounds, confidences, label="Confidence", color="#4CAF50", linewidth=1.5)
    ax.axhline(y=0.3, color="#FF9800", linestyle="--", label="Fallback threshold", linewidth=1)
    ax.set_xlabel("Round")
    ax.set_ylabel("Confidence")
    ax.set_title("Consensus Confidence (Fallback threshold = 0.3)")
    ax.legend()
    ax.grid(True, alpha=0.3)

    # Error convergence
    ax = axes[1, 1]
    errors = [abs(cv - target) for cv in consensus_values]
    ax.plot(rounds, errors, label="|Consensus - Target|", color="#9C27B0", linewidth=1.5)
    ax.set_xlabel("Round")
    ax.set_ylabel("Absolute Error")
    ax.set_title("Error Convergence")
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path / "hivemind_curves.png", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved: {output_path / 'hivemind_curves.png'}")

    # ── Fallback timeline (if any) ──
    if summary["fallback_summary"]["fallback_count"] > 0:
        fig2, ax2 = plt.subplots(figsize=(12, 4))
        fallback_events = summary["fallback_summary"]["fallback_count"]
        fallback_rounds = [l["round"] for l in logs if l.get("fallback_triggered")]
        consensus_at_fallback = [l.get("consensus_value", 0) for l in logs if l.get("fallback_triggered")]
        ax2.plot(rounds, consensus_values, label="Consensus", color="#2196F3", linewidth=1.5)
        ax2.axhline(y=target, color="#F44336", linestyle="--", label="Target", linewidth=1)
        ax2.scatter(fallback_rounds, consensus_at_fallback, color="#FF9800", s=50,
                    zorder=5, label="Fallback triggered", marker='v')
        ax2.set_xlabel("Round")
        ax2.set_ylabel("Consensus Value")
        ax2.set_title(f"Fallback Mechanism Timeline ({fallback_events} events)")
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(output_path / "hivemind_fallback.png", dpi=150, bbox_inches='tight')
        plt.close()
        print(f"Saved: {output_path / 'hivemind_fallback.png'}")

    # ── Proposal scatter + consensus ──
    fig3, ax3 = plt.subplots(figsize=(12, 6))
    for mid in module_ids:
        proposal_values = []
        proposal_rounds = []
        for l in logs:
            ps = l.get("proposals", [])
            for p in ps:
                if p[0] == mid:
                    proposal_rounds.append(l["round"])
                    proposal_values.append(p[1])
        if proposal_rounds:
            ax3.scatter(proposal_rounds, proposal_values, label=mid, alpha=0.6, s=15)

    ax3.axhline(y=target, color="#F44336", linestyle="--", label="Target", linewidth=1.5)
    ax3.plot(rounds, consensus_values, label="Consensus", color="#2196F3", linewidth=1.5, alpha=0.7)
    ax3.set_xlabel("Round")
    ax3.set_ylabel("Proposal Value")
    ax3.set_title("Module Proposals + Consensus Convergence")
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path / "hivemind_proposals.png", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved: {output_path / 'hivemind_proposals.png'}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="HiveMind MVP Visualization")
    parser.add_argument("--input", type=str, default="./output", help="Simulation results directory")
    parser.add_argument("--output", type=str, default="./output", help="Chart output directory")
    args = parser.parse_args()
    logs, summary = load_results(args.input)
    plot_energy_curves(logs, summary, args.output)


if __name__ == "__main__":
    main()
