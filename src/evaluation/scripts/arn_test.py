if __name__ == "__main__":
    import os
    import sys

    # --- Python Path Setup ---
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    import seaborn as sns
    import numpy as np
    import matplotlib.pyplot as plt

    from simulator.engine.random import RandomManager, RandomGenerator

    # Seaborn style
    sns.set_theme(style="whitegrid")

    # --- Random setup ---
    n_samples = 10000
    rm = RandomManager()
    rm_antithetic = RandomManager(antithetic=True)

    rg1 = RandomGenerator(rm, "TEST/STREAM1")
    rg2 = RandomGenerator(rm, "TEST/STREAM2")
    rg3 = RandomGenerator(rm, "TEST/STREAM3")

    rg1_antithetic = RandomGenerator(rm_antithetic, "TEST/STREAM1")
    rg2_antithetic = RandomGenerator(rm_antithetic, "TEST/STREAM2")
    rg3_antithetic = RandomGenerator(rm_antithetic, "TEST/STREAM3")

    dummy_metric = []
    dummy_metric_antithetic = []

    for _ in range(n_samples):
        dummy_metric.append(rg1.uniform() + rg2.nakagami(2.0) + rg3.normal())
        dummy_metric_antithetic.append(
            rg1_antithetic.uniform()
            + rg2_antithetic.nakagami(2.0)
            + rg3_antithetic.normal()
        )

    correlation = np.corrcoef(dummy_metric, dummy_metric_antithetic)[0, 1]

    print(f"Correlation between the two metrics: {correlation:.4f}")
    print(f"Mean of the first metric: {np.mean(dummy_metric):.4f}")
    print(f"Mean of the antithetic metric: {np.mean(dummy_metric_antithetic):.4f}")
    print(f"Variance of the first metric: {np.var(dummy_metric):.4f}")
    print(f"Variance of the antithetic metric: {np.var(dummy_metric_antithetic):.4f}")
    print("Close the plots to end the test.")

    # --- Plotting ---
    lims = [
        min(min(dummy_metric), min(dummy_metric_antithetic)),
        max(max(dummy_metric), max(dummy_metric_antithetic)),
    ]

    figsize = (25, 15)
    fontsize = 23

    fig, axes = plt.subplots(1, 2, figsize=figsize)

    # Scatter plot
    sns.scatterplot(
        x=dummy_metric,
        y=dummy_metric_antithetic,
        alpha=0.3,
        s=10,
        edgecolor=None,
        ax=axes[0],
    )
    axes[0].plot(lims, lims, "r--", linewidth=1, label="y = x")
    axes[0].set_xlabel("Metric", fontsize=fontsize)
    axes[0].set_ylabel("Antithetic Metric", fontsize=fontsize)
    axes[0].set_title(f"Scatter plot (ρ = {correlation:.2f})", fontsize=fontsize)
    axes[0].legend(fontsize=fontsize)

    # Hexbin plot
    hb = axes[1].hexbin(
        dummy_metric, dummy_metric_antithetic, gridsize=60, cmap="Blues"
    )
    fig.colorbar(hb, ax=axes[1], label="Counts")
    axes[1].plot(lims, lims, "r--", linewidth=1)
    axes[1].set_xlabel("Metric", fontsize=fontsize)
    axes[1].set_ylabel("Antithetic Metric", fontsize=fontsize)
    axes[1].set_title(f"Hexbin plot (ρ = {correlation:.2f})", fontsize=fontsize)

    plt.tight_layout()
    plt.show()
