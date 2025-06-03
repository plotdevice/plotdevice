#!/usr/bin/env python3
"""
Framework size reduction script for PlotDevice
Removes unused Python standard library modules to reduce the framework size
"""

import shutil
import sys
from pathlib import Path

# standard library modules to remove (organized by reason)
REMOVE_MODULES = [
    # test suites & demos
    'test', 'turtledemo', 'idlelib',

    # build/packaging tools
    'ensurepip', 'venv', 'lib2to3',

    # documentation
    'pydoc', 'pydoc_data',

    # GUI/TUI frameworks
    'tkinter', 'curses'
]

def main():
    """Remove unused modules from Python framework"""
    print("Optimizing Python Framework for PlotDevice...")
    
    # find framework path
    framework = Path("Python.framework/Versions/Current")
    if not framework.exists():
        print("Error: Framework not found - run 'make Python.framework' first")
        sys.exit(1)
    
    # find stdlib directory
    stdlib = next(framework.glob("lib/python*"), None)
    if not stdlib:
        print("Error: Python stdlib not found")
        sys.exit(1)
    
    # get directory size
    def get_size(path):
        """Get directory size in MB"""
        total_bytes = 0
        for file_path in path.rglob('*'):
            if file_path.is_file():
                total_bytes += file_path.stat().st_size
        
        # convert bytes to MB
        return total_bytes / 1024 / 1024
    
    initial_size = get_size(framework)
    
    # step 1: remove unused modules
    print("\nRemoving unused modules...")
    removed = 0
    for module in REMOVE_MODULES:
        module_path = stdlib / module
        if module_path.exists():
            shutil.rmtree(module_path)
            print(f"✓ Removed {module}")
            removed += 1
    
    # measure size after module removal
    post_modules_size = get_size(framework)
    module_savings = initial_size - post_modules_size
    
    # step 2: remove all __pycache__ directories (old cache + any existing bytecode)
    # this saves ~19MB and Python will recompile modules on-demand at runtime
    print("\nCleaning up cache directories...")
    cache_removed = 0
    for cache in stdlib.rglob("__pycache__"):
        shutil.rmtree(cache)
        cache_removed += 1
    
    # measure final size
    final_size = get_size(framework)
    cache_savings = post_modules_size - final_size
    total_savings = initial_size - final_size
    
    # results
    print("\nResults:")
    print(f"   Modules removed: {removed}/{len(REMOVE_MODULES)} (saved {module_savings:.1f}MB)")
    print(f"   Cache dirs removed: {cache_removed} (saved {cache_savings:.1f}MB)")
    print(f"   Total: {initial_size:.1f}MB → {final_size:.1f}MB")
    print(f"   Total saved: {total_savings:.1f}MB ({total_savings/initial_size*100:.1f}%)")

if __name__ == "__main__":
    main()