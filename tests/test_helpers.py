# tests/test_helpers.py
import os
import sys
import importlib

def import_source_module(module_name):
    """
    Import a module from the source directory, handling different project structures.
    """
    # Try different import strategies
    for module_path in [
        f"src.{module_name}",           # Direct from src/
        f"clinical_trial_matcher.{module_name}",  # From installed package
        module_name                      # Direct import
    ]:
        try:
            return importlib.import_module(module_path)
        except ImportError:
            continue

    # If we get here, none of the import strategies worked
    raise ImportError(f"Could not import module {module_name}")

# Examples of how to import source modules using this helper
# parseXMLs = import_source_module("parseXMLs")
# createCorpusDB = import_source_module("createCorpusDB")