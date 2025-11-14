import sys
import os
import subprocess
import itertools
import argparse
import multiprocessing
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Tuple
from tqdm import tqdm

# --- Static Parameter Definitions ---
# can be overridden by command-line arguments

TOPOLOGIES = [
    #"linear",
    #"ring",
    #"grid",
    "random",
    #"star"
]
CHANNELS = [
    #"ideal",
    "stable",
    #"lossy"
]
NUM_NODES = 20
TX_POWER = 10.0        # in dBm
SIM_TIME = 1800.0     # 30 minutes
APP_DELAY = 130.0
MEAN_INTERARRIVAL = 30.0
DSPACE_STEP = 1.0

# --- Environment Setup ---
PYTHON_EXE = sys.executable  # Use the same Python interpreter running this script (for venv activation)
SIMULATION_MODULE = "src.experiments.run_simulation"


def run_job_worker(job_params: dict) -> Tuple[dict, bool, str]:
    """
    Worker function for the process pool, executes a single simulation run as a subprocess
    
    Returns: (job_parameters, success, output_or_error_message)
    """
    # Build the command
    command = [
        PYTHON_EXE,
        "-m", SIMULATION_MODULE,
        "--topology", job_params["topology"],
        "--channel", job_params["channel"],
        "--num_nodes", str(job_params["num_nodes"]),
        "--tx_power", str(job_params["tx_power"]),
        "--sim_time", str(job_params["sim_time"]),
        "--sim_seed", str(job_params["sim_seed"]),
        "--topo_seed", str(job_params["topo_seed"]),
        "--app_delay", str(job_params["app_delay"]),
        "--mean_interarrival", str(job_params["mean_interarrival"]),
        "--dspace_step", str(job_params["dspace_step"]),
        "--out_dir", job_params["out_dir"]
    ]

    if job_params["antithetic"]:
        command.append("--antithetic")

    if job_params["verbose"]:
        command.append("--verbose")
    
    try:
        result = subprocess.run(
            command, 
            check=True,
            text=True, 
            capture_output=True, 
            encoding='utf-8'
        )
        
        return (job_params, True, "SUCCESS")

    except subprocess.CalledProcessError as e:
        job_id = f"Topo={job_params['topology']}, Chan={job_params['channel']}, SimSeed={job_params['sim_seed']}"
        error_msg = f"ERROR for {job_id} (return code: {e.returncode}):\n"
        error_msg += f"--- STDOUT ---\n{e.stdout}\n"
        error_msg += f"--- STDERR ---\n{e.stderr}\n"
        return (job_params, False, error_msg)
    
    except Exception as e:
        return (job_params, False, f"CRITICAL WORKER ERROR: {str(e)}")


def main_orchestrator():
    """
    Main Orchestrator function.
    """
    
    # --- command-line args for the orchestrator ---
    parser = argparse.ArgumentParser(description="Parallel Batch Orchestrator")

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose monitor output for all sub-runs (default: False)"
    )

    parser.add_argument(
        "-w", "--workers",
        type=int,
        default=multiprocessing.cpu_count(),
        help=f"Number of parallel worker processes (default: all CPUs = {multiprocessing.cpu_count()})"
    )
    parser.add_argument(
        "-n", "--replications",
        type=int,
        default=100,
        help="Number of replications (Monte Carlo runs) per configuration"
    )
    parser.add_argument(
        "--base_sim_seed",
        type=int,
        default=12345,
        help="Starting seed for simulation replications"
    )
    parser.add_argument(
        "--topo_seed",
        type=int,
        default=42,
        help="*Single* seed used for all stochastic topologies"
    )

    parser.add_argument(
        "--antithetic",
        action="store_true",
        help="Run N replications as N/2 antithetic pairs"
    )
    
    args = parser.parse_args()

    # --- Create Output Directory and Job List ---
    TIMESTAMP = datetime.now().strftime("%Y%m%d_%H-%M-%S")
    OUTPUT_BASE_DIR = Path(f"results/batch_{TIMESTAMP}")
    OUTPUT_BASE_DIR.mkdir(parents=True, exist_ok=True)
    
    all_jobs: List[Dict[str, Any]] = []
    
    param_sweep = list(itertools.product(TOPOLOGIES, CHANNELS))

    print("Generating job list...")
    
    if args.antithetic:
        if args.replications % 2 != 0:
            print(f"ERROR: Antithetic mode requires an even number of replications (got {args.replications}).", file=sys.stderr)
            print("Please use -n 100 (for 50 pairs), -n 20 (for 10 pairs), etc.", file=sys.stderr)
            sys.exit(1)
        
        num_pairs = args.replications // 2
        print(f"Antithetic mode enabled. Generating {num_pairs} pairs ({args.replications} total runs)...")
        
        for (topo, chan) in param_sweep:
            for i in range(num_pairs):
                # shared seed for the antithetic pair
                pair_seed = args.base_sim_seed + i
                
                # Job 1: standard (U)
                job_std = {
                    "verbose": args.verbose,
                    "sim_seed": pair_seed,
                    "antithetic": False,
                    "topology": topo, "channel": chan, "num_nodes": NUM_NODES,
                    "tx_power": TX_POWER, "sim_time": SIM_TIME, "app_delay": APP_DELAY,
                    "mean_interarrival": MEAN_INTERARRIVAL, "dspace_step": DSPACE_STEP,
                    "topo_seed": args.topo_seed, "out_dir": str(OUTPUT_BASE_DIR)
                }
                all_jobs.append(job_std)
                
                # Job 2: antithetic (1-U)
                job_anti = {
                    "verbose": args.verbose,
                    "sim_seed": pair_seed, # SAME SEED
                    "antithetic": True,
                    "topology": topo, "channel": chan, "num_nodes": NUM_NODES,
                    "tx_power": TX_POWER, "sim_time": SIM_TIME, "app_delay": APP_DELAY,
                    "mean_interarrival": MEAN_INTERARRIVAL, "dspace_step": DSPACE_STEP,
                    "topo_seed": args.topo_seed, "out_dir": str(OUTPUT_BASE_DIR)
                }
                all_jobs.append(job_anti)

    else:
        # standard Monte Carlo simulations
        print(f"Standard mode. Generating {args.replications} independent replications...")
        for (topo, chan) in param_sweep:
            for i in range(args.replications):
                current_sim_seed = args.base_sim_seed + i
                job = {
                    "verbose": args.verbose,
                    "sim_seed": current_sim_seed,
                    "antithetic": False,
                    "topology": topo, "channel": chan, "num_nodes": NUM_NODES,
                    "tx_power": TX_POWER, "sim_time": SIM_TIME, "app_delay": APP_DELAY,
                    "mean_interarrival": MEAN_INTERARRIVAL, "dspace_step": DSPACE_STEP,
                    "topo_seed": args.topo_seed, "out_dir": str(OUTPUT_BASE_DIR)
                }
                all_jobs.append(job)

    # --- Parallel Execution ---
    num_jobs = len(all_jobs)
    num_workers = min(args.workers, num_jobs)
    
    if num_workers < args.workers:
        print(f"Warning: Number of workers ({args.workers}) exceeds number of jobs ({num_jobs}). Using {num_workers} workers.")
        

    print("\n" + "="*79)
    print(f"Starting Parallel Simulation Batch")
    print(f"Timestamp: {TIMESTAMP}")
    print(f"Results Directory: {OUTPUT_BASE_DIR}")
    print(f"Total configurations: {len(param_sweep)}")
    print(f"Replications per config: {args.replications}")
    print(f"TOTAL JOBS: {num_jobs}")
    print(f"PARALLEL WORKERS: {num_workers}")
    print(f"Base Simulation Seed: {args.base_sim_seed}")
    print(f"Common Topology Seed: {args.topo_seed}")
    print("="*79 + "\n")

    failed_jobs = []
    
    # Use 'imap_unordered' with 'tqdm' for a progress bar
    # that updates as jobs finish (out of order)
    with multiprocessing.Pool(processes=num_workers) as pool:
        try:
            results_iterable = pool.imap_unordered(run_job_worker, all_jobs)
            
            for (job_params, success, message) in tqdm(results_iterable, total=num_jobs, desc="Running Jobs"):
                if not success:
                    failed_jobs.append((job_params, message))

        except KeyboardInterrupt:
            print("\n!!! KEYBOARD INTERRUPT RECEIVED !!! Forcibly terminating workers...", file=sys.stderr)
            pool.terminate()
            pool.join()
            sys.exit(1)

    # --- Final Report ---
    print("\n" + "="*79)
    print("Batch Execution Completed.")
    
    if not failed_jobs:
        print("ALL JOBS COMPLETED SUCCESSFULLY.")
        print(f"Total individual simulations run: {num_jobs}")
    else:
        print(f"ERROR: {len(failed_jobs)} OF {num_jobs} JOBS FAILED.")
        print("Error details saved to 'FAILED_JOBS_LOG.txt' in the results directory.")
        
        log_path = OUTPUT_BASE_DIR / "FAILED_JOBS_LOG.txt"
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write(f"Failure Report for Batch: {TIMESTAMP}\n")
            f.write(f"Failed jobs: {len(failed_jobs)}/{num_jobs}\n")
            f.write("="*79 + "\n\n")
            for (job, error) in failed_jobs:
                f.write(f"--- FAILED JOB ---\n")
                f.write(f"Parameters: {job}\n")
                f.write(f"Error: {error}\n\n")
    
    print(f"Results saved in: {OUTPUT_BASE_DIR}")
    print("="*79)

if __name__ == "__main__":
    # This block executes when the script is run directly
    # or as a module (e.g., `python -m src.evaluation.run_batch`).
    # The module execution (`-m`) correctly handles Python's import paths.
    main_orchestrator()