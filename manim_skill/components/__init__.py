"""Auto-discovers and imports every component module in this package so
each component self-registers via the @register decorator. New component
files need no wiring here — just add the file to this package.
"""

from __future__ import annotations

import importlib
import pkgutil

for _module_info in pkgutil.iter_modules(__path__):
    if _module_info.name != "base":
        importlib.import_module(f"{__name__}.{_module_info.name}")
