"""Filesystem scanner: walks a tree, aggregates sizes per directory, classifies each.

Uses os.scandir for speed. Reports progress via callback. Handles permission
errors gracefully (skips and counts them — never crashes the scan).
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from safety import Verdict, classify


@dataclass
class Node:
    path: str
    name: str
    size: int = 0          # bytes (recursive, for dirs)
    file_count: int = 0    # recursive
    is_dir: bool = True
    verdict: Optional[Verdict] = None
    children: list["Node"] = field(default_factory=list)
    error: Optional[str] = None


class Scanner:
    def __init__(self, progress_cb: Optional[Callable[[str, int], None]] = None):
        self.progress_cb = progress_cb or (lambda path, count: None)
        self._cancel = threading.Event()
        self._scanned = 0
        self._last_report = 0.0
        self.errors: list[str] = []

    def cancel(self) -> None:
        self._cancel.set()

    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def _report(self, path: str) -> None:
        self._scanned += 1
        now = time.monotonic()
        if now - self._last_report > 0.1:
            self._last_report = now
            self.progress_cb(path, self._scanned)

    def scan(self, root: str) -> Node:
        root = os.path.abspath(root)
        node = Node(path=root, name=root, is_dir=True, verdict=classify(root))
        self._walk(node)
        return node

    def _walk(self, node: Node) -> None:
        if self._cancel.is_set():
            return
        try:
            entries = list(os.scandir(node.path))
        except (PermissionError, OSError) as e:
            node.error = str(e)
            self.errors.append(f"{node.path}: {e}")
            return

        for entry in entries:
            if self._cancel.is_set():
                return
            try:
                if entry.is_symlink():
                    # Don't follow symlinks/junctions — risk of loops & double-counting
                    continue
                if entry.is_dir(follow_symlinks=False):
                    child = Node(
                        path=entry.path,
                        name=entry.name,
                        is_dir=True,
                        verdict=classify(entry.path),
                    )
                    self._walk(child)
                    node.children.append(child)
                    node.size += child.size
                    node.file_count += child.file_count
                    self._report(entry.path)
                else:
                    try:
                        st = entry.stat(follow_symlinks=False)
                        size = st.st_size
                    except OSError:
                        size = 0
                    node.size += size
                    node.file_count += 1
                    # We don't store individual file Nodes — would balloon memory.
                    # Files are summarized into their parent dir.
            except (PermissionError, OSError) as e:
                self.errors.append(f"{entry.path}: {e}")
                continue
