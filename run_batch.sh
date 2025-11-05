#!/bin/bash
# =============================================================================
# Simulation Batch Runner
#
# This script runs a parameter sweep for the specified Python simulation module.
# It iterates through all defined topologies and channel conditions.
#
# Place this script in the project root directory (alongside the 'src/' folder).
# =============================================================================

# --- 1. Global Simulation Parameters ---
# (You can easily change these variables)

# The Python module to run (relative to the project root)
# This allows you to easily switch to 'src.evaluation.random_traffic' etc.
PYTHON_MODULE="src.evaluation.pingpong"

# Number of nodes for all simulations
NUM_NODES=20

# DSpace grid resolution (meters per point)
DSPACE_STEP=1.0


# --- 2. Parameter Sweep Arrays ---
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


# --- 3. Simulation Execution ---

echo "Starting simulation sweep..."
echo "====================================================="
echo "Target Module:   $PYTHON_MODULE"
echo "Nodes per sim:   $NUM_NODES"
echo "DSpace Step:     $DSPACE_STEP"
echo "====================================================="

# Get the directory where this script is located (the project root)
# and add 'src' to the PYTHONPATH. This ensures Python can find the
# 'evaluation' module even when run from the root.
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
export PYTHONPATH="$SCRIPT_DIR/src"

TOTAL_SIMS=$(( ${#TOPOLOGIES[@]} * ${#CHANNELS[@]} ))
CURRENT_SIM=1

# Iterate over all topologies
for topo in "${TOPOLOGIES[@]}"; do
  # Iterate over all channel conditions
  for chan in "${CHANNELS[@]}"; do
    
    echo ""
    echo "--- Running Sim ($CURRENT_SIM / $TOTAL_SIMS): Topo=$topo, Chan=$chan ---"
    
    # Construct and execute the command
    python3 -m "evaluation.pingpong" \
      --topology "$topo" \
      --channel "$chan" \
      --num_nodes "$NUM_NODES" \
      --dspace_step "$DSPACE_STEP"
    
    # Check the exit code of the last command (like '&&')
    if [ $? -ne 0 ]; then
      echo ""
      echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
      echo "ERROR: Simulation failed for Topo=$topo, Chan=$chan"
      echo "Stopping script."
      echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
      exit 1
    fi
    
    CURRENT_SIM=$((CURRENT_SIM + 1))
    
  done
done

echo ""
echo "====================================================="
echo "Simulation sweep completed successfully ($TOTAL_SIMS simulations)."
echo "====================================================="