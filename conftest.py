"""
Pytest configuration file

Configures Python path to include the common layer for testing.
"""

import sys
import os

# Add the common layer to the Python path
common_layer_path = os.path.join(
    os.path.dirname(__file__),
    "layers",
    "common",
    "python"
)
sys.path.insert(0, common_layer_path)

# Add the functions directory for testing Lambda handlers
functions_path = os.path.join(os.path.dirname(__file__), "functions")
sys.path.insert(0, functions_path)
