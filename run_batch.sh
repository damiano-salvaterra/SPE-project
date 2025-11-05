#!/bin/bash
# =============================================================================
# Simulation Batch Runner
#
# This script runs a parameter sweep for the specified Python simulation module.
# It iterates through all defined topologies and channel conditions.
#
# =============================================================================

# --- Global Simulation Parameters ---

PYTHON_MODULE="evaluation.run_scenario"

# Application to run for this entire sweep
# Options: "pingpong" or "random_traffic"
APP_TO_RUN="random_traffic"

# App-specific parameters (ignored if not applicable)
MEAN_INTERARRIVAL=30.0 # For 'random_traffic'

# Number of nodes for all simulations
NUM_NODES=20

# DSpace grid resolution (meters per point)
DSPACE_STEP=1.0


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
echo "Nodes per sim:   $NUM_NODES"
echo "DSpace Step:     $DSPACE_STEP"
if [ "$APP_TO_RUN" == "random_traffic" ]; then
  echo "Mean Interarrival: $MEAN_INTERARRIVAL s"
fi
echo "====================================================="

# Get the directory where this script is located (the project root)
# and add 'src' to the PYTHONPATH. This ensures Python can find the
# module even when run from the root.
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
export PYTHONPATH="$SCRIPT_DIR/src"

TOTAL_SIMS=$(( ${#TOPOLOGIES[@]} * ${#CHANNELS[@]} ))
CURRENT_SIM=1

# Iterate over all topologies
for topo in "${TOPOLOGIES[@]}"; do
  # Iterate over all channel conditions
  for chan in "${CHANNELS[@]}"; do
    
    echo ""
    echo "--- Running Sim ($CURRENT_SIM / $TOTAL_SIMS): App=$APP_TO_RUN, Topo=$topo, Chan=$chan ---"
    
    # Construct and execute the command
    # We pass all parameters: the Python script's argparse will
    # ignore the ones it doesn't recognize
    python3 -m "$PYTHON_MODULE" \
      --app "$APP_TO_RUN" \
      --topology "$topo" \
      --channel "$chan" \
      --num_nodes "$NUM_NODES" \
      --dspace_step "$DSPACE_STEP" \
      --mean_interarrival "$MEAN_INTERARRIVAL"
    
    # Check the exit code of the last command
    if [ $? -ne 0 ]; then
      echo ""
      echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
      echo "ERROR: Simulation failed for App=$APP_TO_RUN, Topo=$topo, Chan=$chan"
      echo "Stopping script."
      echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
      exit 1
    fi
    
    CURRENT_SIM=$((CURRENT_SIM + 1))
    
  done
done

echo " "
echo "====================================================="
echo "Simulation sweep completed successfully ($TOTAL_SIMS simulations)."
echo "====================================================="