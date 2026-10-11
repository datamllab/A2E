#!/usr/bin/env python3
"""Small file-copy helpers shared by open source Docker execution scripts."""

from __future__ import annotations

import shutil
from pathlib import Path


def copy_path_preserving_symlinks(src: str | Path, dst: str | Path) -> bool:
    """Copy a file or directory if it exists, preserving symlinks in directories."""
    src = Path(src)
    dst = Path(dst)
    if not src.exists():
        return False
    if src.is_dir():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst, symlinks=True)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    return True
