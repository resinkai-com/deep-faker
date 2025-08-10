"""Command-line interface for deep_faker simulations."""

import argparse
import importlib.util
import os
import sys


def load_simulation_module(file_path: str):
    """Load a simulation module from file path."""
    spec = importlib.util.spec_from_file_location("simulation", file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load simulation from {file_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules["simulation"] = module
    spec.loader.exec_module(module)
    return module


def run_simulation(file_path: str, chdir: str = None):
    """Run a simulation from a file."""
    # Change directory if specified
    original_cwd = os.getcwd()
    if chdir:
        os.chdir(chdir)
        print(f"Changed directory to: {chdir}")

    try:
        # Convert to absolute path after changing directory if needed
        if not os.path.isabs(file_path):
            file_path = os.path.abspath(file_path)

        # Load and run the simulation
        print(f"Loading simulation from: {file_path}")
        module = load_simulation_module(file_path)

        # Look for a 'sim' variable in the module (common convention)
        if hasattr(module, "sim"):
            sim = module.sim
            print(f"Running simulation: {sim}")
            sim.run()
        else:
            # Look for any Simulation instance
            from .simulation import Simulation

            sim_instances = [
                obj for obj in module.__dict__.values() if isinstance(obj, Simulation)
            ]
            if sim_instances:
                sim = sim_instances[0]
                print(f"Running simulation: {sim}")
                sim.run()
            else:
                raise ValueError("No Simulation instance found in module")

    finally:
        # Restore original directory
        os.chdir(original_cwd)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Run deep_faker simulations", prog="deepfaker"
    )

    parser.add_argument(
        "config", help="Path to simulation config file (e.g., ecommerce.py)"
    )

    parser.add_argument("--chdir", help="Change to directory before running simulation")

    args = parser.parse_args()

    try:
        run_simulation(args.config, args.chdir)
    except Exception as e:
        print(f"Error running simulation: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
