#!/bin/bash
# =============================================================================
# This script is an entry point for running a *SINGLE* simulation.
# 1. It activates the Python virtual environment.
# 2. It executes the Python single simulation script
#    (src.experimetns.run_simulation) as a module.
# 3. It passes all command-line arguments (e.g., --topology, --sim_seed)
#    directly to the Python script using "$@".
# =============================================================================

# --- 1. Environment Setup ---
# Find the venv relative to the project root (where this script lives)
VENV_PATH=".venv/bin/activate"

if [ -f "$VENV_PATH" ]; then
    echo "Activating Python virtual environment from $VENV_PATH..."
    source "$VENV_PATH"
else
    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    echo "ERROR: Virtual environment not found at $VENV_PATH"
    echo "Please ensure the .venv folder exists in the project root."
    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    exit 1
fi

# --- 2. Run Single Simulation ---
# Run the simulation script as a module from the src direcstory.
echo "Starting Python single simulation (src.experiments.run_simulation)..."
echo "Passing arguments: $@"
python3 -m src.experiments.run_simulation "$@"