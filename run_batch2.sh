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

REPLICATIONS=100       # Total replications *per* parameter combination
BASE_SEED=12345       # Starting seed. Run 'i' will use (BASE_SEED + i)

APPS=(
    "poisson_traffic"
    # "pingpong"
)
TOPOLOGIES=(
    "linear"
    "ring"
    "grid"
    "random"
    "star"
    #"cluster-tree"
)
CHANNELS=( #TODO: try to change the shadowing model and use shadowing at the receiver
    #"ideal"
    #"stable"
    #"lossy"
    #"unstable"
    stable_mid_pl
    stable_high_pl
)

# --- 2. Static Simulation Parameters ---
# These parameters are fixed for all runs in this batch.

NUM_NODES=20
TX_POWER=5        # in dBm
SIM_TIME=1800.0     # 30 minutes
APP_DELAY=130.0     # ~2 min (allows TARP to stabilize before traffic)
MEAN_INTERARRIVAL=30.0 # For 'poisson_traffic' (30s avg per node)
DSPACE_STEP=1.0

# --- NEW: Parameters for ClusterTreeTopology ---
#
# These are used *only* when 'cluster-tree' is in the TOPOLOGIES array.
# They are ignored by other topology types (like 'random').
# This configuration generates: 1 (Root) + 5 (L1) + 10 (L2) + 20 (L3) = 36 Nodes
DEPTH=3                 # Total levels *below* the root
NUM_CLUSTERS=5          # Number of nodes at Level 1 (Children of Root)
NODES_PER_CLUSTER=3     # Total nodes *in* a cluster (1 Parent + N-1 Children)
CLUSTER_RADIUS=100.0    # Radius for L1 node placement
NODE_RADIUS=25.0        # Radius for L2+ node placement (around their parent)
# --- End of New Parameters ---

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
# NOTE: We only create the base directory. Python script handles subdirs.
mkdir -p "$OUTPUT_BASE_DIR" 
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

      # --- This combination is now just for logging ---
      echo
      echo
      echo "===================================================================================================================="
      echo "-----------------------------------------------------"
      echo "Running Batch ($CURRENT_CONFIG / $TOTAL_CONFIGS): App=$app, Topo=$topo, Chan=$chan, tx_dBm=$TX_POWER dBm"
      echo "Replications: $REPLICATIONS"
      echo "-----------------------------------------------------"
      echo "===================================================================================================================="
      echo
      echo "---------------------------------------------------------------------------------------------------------------------"


      # --- Replication Loop (Monte Carlo) ---
      for (( i=0; i<$REPLICATIONS; i++ )); do
        
        CURRENT_SEED=$((BASE_SEED + i))
        echo
        echo "===================================================================================================================="
        echo "  -> Starting Replication $((i+1))/$REPLICATIONS (Seed: $CURRENT_SEED)..."
        echo "===================================================================================================================="
        echo

        # Call the Python script for a SINGLE run
        # Pass the BATCH BASE directory. The Python script
        # will create the app/topology/channel subdirectories itself.
        python -m evaluation.run_simulation_refactor \
          --app "$app" \
          --topology "$topo" \
          --channel "$chan" \
          --num_nodes "$NUM_NODES" \
          --tx_power "$TX_POWER" \
          --sim_time "$SIM_TIME" \
          --seed "$CURRENT_SEED" \
          --app_delay "$APP_DELAY" \
          --mean_interarrival "$MEAN_INTERARRIVAL" \
          --dspace_step "$DSPACE_STEP" \
          --out_dir "$OUTPUT_BASE_DIR" \

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
