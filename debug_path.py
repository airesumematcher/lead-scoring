#!/usr/bin/env python3
"""Debug script to directly test _load_model_metrics."""

import sys
from pathlib import Path
import json
import pickle

sys.path.insert(0, str(Path(__file__).parent / "src"))

# Manually replicate what _load_model_metrics should be doing
models_dir = Path(__file__).parent / "models"
results_path = models_dir / "model_comparison_results.json"

print(f"Manual test:")
print(f"  Current file: {Path(__file__)}")
print(f"  Parent (project root): {Path(__file__).parent}")
print(f"  Models dir: {models_dir}")
print(f"  Results path: {results_path}")
print(f"  Exists: {results_path.exists()}")

# Now test what Path(__file__).parent.parent.parent does from within the handlers module
# The handlers.py is at: src/lead_scoring/api/handlers.py
# So from there:
# - parent (/) = src/lead_scoring/api/
# - parent.parent = src/lead_scoring/
# - parent.parent.parent = src/
# Which is WRONG! It should be:
# - src/lead_scoring/api/handlers.py
# - parent.parent = src/lead_scoring/
# - parent.parent.parent = out of the project!

print(f"\n\nPath resolution from handlers.py perspective:")
# Simulate being in the handlers.py file
handlers_file = Path(__file__).parent / "src" / "lead_scoring" / "api" / "handlers.py"
print(f"  handlers.py location: {handlers_file}")
print(f"  parent: {handlers_file.parent}")
print(f"  parent.parent: {handlers_file.parent.parent}")
print(f"  parent.parent.parent: {handlers_file.parent.parent.parent}")
print(f"  parent.parent.parent / models: {handlers_file.parent.parent.parent / 'models'}")

# The issue is that models should be at: src/lead_scoring/../../../models
# which is: PROJECT_ROOT/models
# So from handlers.py (src/lead_scoring/api/handlers.py), it should be:
# ../../.../models which is: parent.parent.parent + /models
correct_models_path = handlers_file.parent.parent.parent / "models"
print(f"  This path goes to: {correct_models_path}")
print(f"  Exists: {correct_models_path.exists()}")

if correct_models_path.exists():
    print(f"  Contents: {list(correct_models_path.glob('*.pkl'))[:3]}")
