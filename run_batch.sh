#!/bin/bash
# =============================================================================
# Simulation Batch Runner (Updated for refactored run_scenario.py)
#
# This script runs a parameter sweep for the specified Python simulation module.
# For each combination of Topology and Channel, it executes a *batch* of
# simulation runs (replications) using different seeds, as managed by
# run_scenario.py.
#
# =============================================================================

# --- Global Simulation Parameters ---

PYTHON_MODULE="evaluation.run_scenario"

# Application to run for this entire sweep
# Options: "pingpong" or "poisson_traffic"
APP_TO_RUN="poisson_traffic"

# --- NEW: Batch, Time, and Seed Parameters ---
# These are passed directly to run_scenario.py

# Number of replications (runs) FOR EACH parameter combination
NUM_RUNS_PER_CONFIG=30

# Base seed for the entire sweep.
# run_scenario.py will use (BASE_SEED + i) for each run (0, 1, 2...)
# This ensures replicability.
BASE_SEED=12345

# Simulation time and app delay time (in seconds)
SIMULATION_TIME=1800.0  # 30 minutes total
APP_DELAY=120.0     # 2 minutes before app traffic starts

# --- Scenario Parameters ---

# Number of nodes for all simulations (this is the "requested" number)
NUM_NODES=20

# DSpace grid resolution (meters per point)
DSPACE_STEP=1.0

# App-specific parameters (ignored if not applicable)
MEAN_INTERARRIVAL=30.0 # For 'random_traffic'


# --- Parameter Sweep Arrays ---
# (Add or remove items here to change the sweep)

TOPOLOGIES=(
    "linear"
    "ring"
    "grid"
    "random"
    "star"
    "cluster-tree"
)

CHANNELS=(
    "stable"
    "medium"
    "medium_lossy"
    "harsh_unstable"
    "harsh"
)


# --- Simulation Execution ---

echo "Starting simulation sweep..."
echo "====================================================="
echo "Target Module:   $PYTHON_MODULE"
echo "Application:     $APP_TO_RUN"
echo "Nodes per sim:   $NUM_NODES (requested)"
echo "DSpace Step:     $DSPACE_STEP"
echo "---"
echo "Runs per config: $NUM_RUNS_PER_CONFIG"
echo "Base Seed:       $BASE_SEED"
echo "Sim Time:        $SIMULATION_TIME s"
echo "App Delay Time:    $APP_DELAY s"
if [ "$APP_TO_RUN" == "random_traffic" ]; then
  echo "Mean Interarrival: $MEAN_INTERARRIVAL s"
fi
echo "====================================================="

# Get the directory where this script is located (the project root)
# and add 'src' to the PYTHONPATH.
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
export PYTHONPATH="$SCRIPT_DIR/src"

TOTAL_CONFIGS=$(( ${#TOPOLOGIES[@]} * ${#CHANNELS[@]} ))
CURRENT_CONFIG=1

# Iterate over all topologies
for topo in "${TOPOLOGIES[@]}"; do
  # Iterate over all channel conditions
  for chan in "${CHANNELS[@]}"; do
    
    echo ""
    echo "--- Running Batch ($CURRENT_CONFIG / $TOTAL_CONFIGS): App=$APP_TO_RUN, Topo=$topo, Chan=$chan ---"
    
    # Construct and execute the command
    # We pass all parameters; the Python script's argparse will
    # handle them.
    python3 -m "$PYTHON_MODULE" \
      --app "$APP_TO_RUN" \
      --topology "$topo" \
      --channel "$chan" \
      --num_nodes "$NUM_NODES" \
      --dspace_step "$DSPACE_STEP" \
      --mean_interarrival "$MEAN_INTERARRIVAL" \
      --sim_time "$SIMULATION_TIME" \
      --app_delay "$APP_DELAY" \
      --num_runs "$NUM_RUNS_PER_CONFIG" \
      --base_seed "$BASE_SEED"
    
    # Check the exit code of the last command
    if [ $? -ne 0 ]; then
      echo ""
      echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
      echo "ERROR: Batch failed for App=$APP_TO_RUN, Topo=$topo, Chan=$chan"
      echo "Stopping script."
      echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
      exit 1
    fi
    
    CURRENT_CONFIG=$((CURRENT_CONFIG + 1))
    
  done
done

echo " "
echo "====================================================="
echo "Simulation sweep completed successfully ($TOTAL_CONFIGS batches run)."
echo "====================================================="