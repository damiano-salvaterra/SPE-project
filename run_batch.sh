#!/bin/bash
# =============================================================================
# Minimalist Simulation Batch Runner
#
# This script runs a full parameter sweep for the 'run_simulation.py' script.
# It loops through all combinations of Applications, Topologies, and Channels,
# and for each combination, it runs 'N' independent replications (Monte Carlo runs)
# by calling the Python script with a different seed for each run.
# =============================================================================

# --- 1. Parameter Sweep Definitions ---
# Define the parameters you want to sweep in these arrays.

REPLICATIONS=30       # Total replications *per* parameter combination
BASE_SEED=12345       # Starting seed. Run 'i' will use (BASE_SEED + i)

APPS=(
    "poisson_traffic"
    # "pingpong"
)
TOPOLOGIES=(
    #"linear"
    #"ring"
    #"grid"
    "random"
    "star"
    "cluster-tree"
)
CHANNELS=(
    "stable"
    "lossy"
    "unstable"
)

# --- 2. Static Simulation Parameters ---
# These parameters are fixed for all runs in this batch.

NUM_NODES=20
SIM_TIME=1800.0     # 30 minutes
APP_DELAY=130.0     # ~2 min (allows TARP to stabilize before traffic)
MEAN_INTERARRIVAL=30.0 # For 'poisson_traffic' (30s avg per node)
DSPACE_STEP=1.0

# =============================================================================
# --- 3. Environment Setup (Do not edit below) ---
# =============================================================================

echo "--- Starting Simulation Batch Sweep ---"

# Get the script's directory (project root)
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
VENV_PATH="$SCRIPT_DIR/.venv/bin/activate"

# Activate virtual environment
if [ ! -f "$VENV_PATH" ]; then
    echo "ERROR: Virtual environment not found at $VENV_PATH"
    echo "Please create it: 'python3 -m venv .venv'"
    echo "And install dependencies: 'pip install -r requirements.txt'"
    exit 1
fi
source "$VENV_PATH"

# Set PYTHONPATH to include the 'src' directory
export PYTHONPATH="$SCRIPT_DIR/src"

# Base output directory for all results from this batch
BATCH_TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
OUTPUT_BASE_DIR="$SCRIPT_DIR/results/batch_${BATCH_TIMESTAMP}"
echo "Batch output will be saved to: $OUTPUT_BASE_DIR"

# =============================================================================
# --- 4. Main Execution Loops ---
# =============================================================================

TOTAL_JOBS=0
TOTAL_CONFIGS=$(( ${#APPS[@]} * ${#TOPOLOGIES[@]} * ${#CHANNELS[@]} ))
CURRENT_CONFIG=1

for app in "${APPS[@]}"; do
  for topo in "${TOPOLOGIES[@]}"; do
    for chan in "${CHANNELS[@]}"; do

      # --- Define a unique output directory for this parameter combination ---
      CONFIG_NAME="${app}/${topo}_${chan}_${NUM_NODES}nodes"
      RUN_OUTPUT_DIR="$OUTPUT_BASE_DIR/${CONFIG_NAME}"
      mkdir -p "$RUN_OUTPUT_DIR"

      echo "-----------------------------------------------------"
      echo "Running Batch ($CURRENT_CONFIG / $TOTAL_CONFIGS): App=$app, Topo=$topo, Chan=$chan"
      echo "Replications: $REPLICATIONS, Output Dir: $RUN_OUTPUT_DIR"
      echo "-----------------------------------------------------"

      # --- Replication Loop (Monte Carlo) ---
      for (( i=0; i<$REPLICATIONS; i++ )); do
        
        CURRENT_SEED=$((BASE_SEED + i))
        echo "  -> Starting Replication $((i+1))/$REPLICATIONS (Seed: $CURRENT_SEED)..."

        # Call the Python script for a SINGLE run
        python -m evaluation.run_simulation \
          --app "$app" \
          --topology "$topo" \
          --channel "$chan" \
          --num_nodes "$NUM_NODES" \
          --sim_time "$SIM_TIME" \
          --seed "$CURRENT_SEED" \
          --app_delay "$APP_DELAY" \
          --mean_interarrival "$MEAN_INTERARRIVAL" \
          --dspace_step "$DSPACE_STEP" \
          --out_dir "$RUN_OUTPUT_DIR" # Pass the specific output dir

        # --- Robust Error Checking ---
        # Stop the entire sweep if a single run fails
        if [ $? -ne 0 ]; then
            echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
            echo "ERROR: Python script failed for Seed $CURRENT_SEED!"
            echo "Config: App=$app, Topo=$topo, Chan=$chan"
            echo "Stopping batch script."
            echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
            exit 1 # Exit script with an error code
        fi
        
        TOTAL_JOBS=$((TOTAL_JOBS + 1))
      done # --- End Replication Loop ---

      CURRENT_CONFIG=$((CURRENT_CONFIG + 1))
      
    done # --- End Channel Loop ---
  done # --- End Topology Loop ---
done # --- End App Loop ---

echo "=========================================="
echo "Batch Sweep Completed Successfully."
echo "Total individual simulations run: $TOTAL_JOBS"
echo "Results saved in: $OUTPUT_BASE_DIR"
echo "=========================================="