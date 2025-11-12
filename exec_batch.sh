#!/bin/bash
# =============================================================================
# This script is the main entry point for running simulation batches.
# 1. It activates the Python virtual environment.
# 2. It executes the Python batch orchestrator script
#    (src.experiments.run_batch) as a module.
# 3. It passes all command-line arguments (e.g., --workers, --replications)
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

# --- 2. Run Orchestrator ---
# Run the batch script as a module from the src directory.
# This ensures all Python imports work correctly.
echo "Starting Python batch orchestrator (src.experiments.run_batch)..."
echo "Passing arguments: $@"
python3 -m src.experiments.run_batch "$@"