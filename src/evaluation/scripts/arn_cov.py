from pathlib import Path

import seaborn as sns
import matplotlib.pyplot as plt
import pandas as pd

from ..metrics.results import SimulationResults
from ..metrics.repetition import RepetitionResults


def main():
    sim_folder = Path(
        "results/batch_2025-11-11_23-44-21/poisson_traffic/grid_20N/stable_mid_pl"
    )

    sim = SimulationResults.from_folder(sim_folder)

    print(f"Simulation 0: {sim.repetitions[0]}")
    print(f"Simulation 1: {sim.repetitions[1]}")

    latencies = [
        rep.latency_df["latency"]
        for rep in sim.repetitions
        if not rep.parameters["command_line_arguments"].get("antithetic", False)
    ]
    latencies_antithetic = [
        rep.latency_df["latency"]
        for rep in sim.repetitions
        if rep.parameters["command_line_arguments"].get("antithetic", True)
    ]

    # Merge the series
    # srs_latencies = latencies[0]
    # for sr in latencies[1:]:
    #     srs_latencies = srs_latencies.combine_first(sr)
    # srs_latencies_antithetic = latencies_antithetic[0]
    # for sr in latencies_antithetic[1:]:
    #     srs_latencies_antithetic = srs_latencies_antithetic.combine_first(sr)

    latencies_mean = pd.Series([sr.mean() for sr in latencies])
    latencies_antithetic_mean = pd.Series([sr.mean() for sr in latencies_antithetic])
    srs_latencies = latencies_mean
    srs_latencies_antithetic = latencies_antithetic_mean

    print()
    print(f"Latencies Non-Antithetic:\n{srs_latencies.describe()}")
    print(f"Latencies Antithetic:\n{srs_latencies_antithetic.describe()}")

    print()
    cov_0_1 = srs_latencies.cov(srs_latencies_antithetic)
    print(f"Covariance between Antithetic and non: {cov_0_1}")
    corr_0_1 = srs_latencies.corr(srs_latencies_antithetic)
    print(f"Correlation between Antithetic and non: {corr_0_1}")

    # Scatter plot
    sns.scatterplot(x=srs_latencies, y=srs_latencies_antithetic)
    plt.xlabel("Latencies Non-Antithetic")
    plt.ylabel("Latencies Antithetic")
    plt.title(
        "Scatter Plot of Latencies: Antithetic vs Non-Antithetic"
        + "\n"
        + f"(ρ = {corr_0_1:.2f}, cov = {cov_0_1:.2f})"
    )
    lims = [
        min(min(srs_latencies), min(srs_latencies_antithetic)),
        max(max(srs_latencies), max(srs_latencies_antithetic)),
    ]
    plt.plot(lims, lims, "r--", linewidth=1, label="y = x")

    plt.show()


if __name__ == "__main__":
    main()
