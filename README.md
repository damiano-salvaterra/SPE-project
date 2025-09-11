# SPE-project
Project of The Simulation and Performance Evaluation course @ UNITN

## Pre-commit Hook Setup

This project uses [pre-commit](https://pre-commit.com/) to automatically format code with [Black](https://black.readthedocs.io/) before each commit.

To set up pre-commit hooks, run:

```sh
pip install pre-commit black
pre-commit install
```

To manually run the hooks on all files:

```sh
pre-commit run --all-files
```

This ensures your code is always formatted and consistent before committing.
