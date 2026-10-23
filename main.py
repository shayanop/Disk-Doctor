"""DiskDoctor — safety-aware disk space analyzer for Windows.

Scans a directory tree, classifies each folder by deletion safety, and lets
you send folders to the Recycle Bin with hard safety rails on system paths.

Run:  py main.py        (or)   run.bat
"""

from __future__ import annotations

import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import safety
from recycle import send_to_recycle_bin
from scanner import Node, Scanner


def human_size(n: int) -> str:
    f = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if f < 1024 or unit == "TB":
            return f"{f:.1f} {unit}" if unit != "B" else f"{int(f)} {unit}"
        f /= 1024
    return f"{f:.1f} TB"


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("DiskDoctor — Windows-aware disk analyzer")
        root.geometry("1100x700")

        self.scanner: Scanner | None = None
        self.scan_thread: threading.Thread | None = None
        self.tree_root: Node | None = None
        # Map Treeview iid -> Node
        self.iid_to_node: dict[str, Node] = {}

        self._build_ui()

    # ---- UI ----
    def _build_ui(self) -> None:
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill=tk.X)

        ttk.Label(top, text="Path:").pack(side=tk.LEFT)
        self.path_var = tk.StringVar(value="C:\\")
        self.path_entry = ttk.Entry(top, textvariable=self.path_var, width=60)
        self.path_entry.pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Browse…", command=self._browse).pack(side=tk.LEFT)
        self.scan_btn = ttk.Button(top, text="Scan", command=self._toggle_scan)
        self.scan_btn.pack(side=tk.LEFT, padx=8)

        # Filters
        filt = ttk.Frame(self.root, padding=(8, 0))
        filt.pack(fill=tk.X)
        ttk.Label(filt, text="Show:").pack(side=tk.LEFT)
        self.show = {c: tk.BooleanVar(value=True) for c in (safety.SAFE, safety.REVIEW, safety.RISKY, safety.NEVER)}
        for cat in (safety.SAFE, safety.REVIEW, safety.RISKY, safety.NEVER):
            ttk.Checkbutton(
                filt, text=cat, variable=self.show[cat], command=self._refresh_view
            ).pack(side=tk.LEFT, padx=4)

        # Tree
        mid = ttk.Frame(self.root, padding=8)
        mid.pack(fill=tk.BOTH, expand=True)

        cols = ("size", "files", "category", "reason")
        self.tree = ttk.Treeview(mid, columns=cols, show="tree headings", selectmode="extended")
        self.tree.heading("#0", text="Path")
        self.tree.heading("size", text="Size", command=lambda: self._sort_by("size"))
        self.tree.heading("files", text="Files")
        self.tree.heading("category", text="Category")
        self.tree.heading("reason", text="Why")
        self.tree.column("#0", width=420, stretch=True)
        self.tree.column("size", width=100, anchor=tk.E)
        self.tree.column("files", width=80, anchor=tk.E)
        self.tree.column("category", width=80, anchor=tk.CENTER)
        self.tree.column("reason", width=380, stretch=True)

        for cat, color in safety.CATEGORY_COLOR.items():
            self.tree.tag_configure(cat, foreground=color)

        ysb = ttk.Scrollbar(mid, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=ysb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ysb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<<TreeviewOpen>>", self._on_open)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # Bottom — status + delete
        bot = ttk.Frame(self.root, padding=8)
        bot.pack(fill=tk.X)
        self.status = tk.StringVar(value="Idle. Pick a path and Scan.")
        ttk.Label(bot, textvariable=self.status).pack(side=tk.LEFT)
        self.delete_btn = ttk.Button(bot, text="Send selected to Recycle Bin", command=self._delete_selected, state=tk.DISABLED)
        self.delete_btn.pack(side=tk.RIGHT)
        self.selected_lbl = tk.StringVar(value="")
        ttk.Label(bot, textvariable=self.selected_lbl).pack(side=tk.RIGHT, padx=8)

    def _browse(self) -> None:
        d = filedialog.askdirectory(initialdir=self.path_var.get() or "C:\\")
        if d:
            self.path_var.set(os.path.normpath(d))

    # ---- Scan control ----
    def _toggle_scan(self) -> None:
        if self.scanner and self.scan_thread and self.scan_thread.is_alive():
            self.scanner.cancel()
            self.status.set("Cancelling…")
            return

        path = self.path_var.get().strip()
        if not path or not os.path.isdir(path):
            messagebox.showerror("DiskDoctor", f"Not a directory:\n{path}")
            return

        self.tree.delete(*self.tree.get_children())
        self.iid_to_node.clear()
        self.tree_root = None
        self.scan_btn.config(text="Cancel")
        self.delete_btn.config(state=tk.DISABLED)
        self.status.set(f"Scanning {path}…")

        self.scanner = Scanner(progress_cb=self._on_progress)
        self.scan_thread = threading.Thread(target=self._run_scan, args=(path,), daemon=True)
        self.scan_thread.start()

    def _run_scan(self, path: str) -> None:
        try:
            root = self.scanner.scan(path)
        except Exception as e:  # last-resort guard so the thread never silently dies
            self.root.after(0, lambda: self._scan_done(None, str(e)))
            return
        self.root.after(0, lambda: self._scan_done(root, None))

    def _on_progress(self, path: str, count: int) -> None:
        # Called from scanner thread; marshal to UI thread
        self.root.after(0, lambda: self.status.set(f"Scanned {count:,} dirs… {path[:80]}"))

    def _scan_done(self, root: Node | None, error: str | None) -> None:
        self.scan_btn.config(text="Scan")
        if error:
            self.status.set(f"Error: {error}")
            messagebox.showerror("DiskDoctor", f"Scan failed:\n{error}")
            return
        if root is None:
            self.status.set("Cancelled.")
            return
        self.tree_root = root
        errs = len(self.scanner.errors) if self.scanner else 0
        self.status.set(
            f"Done. Total: {human_size(root.size)} across {root.file_count:,} files. "
            f"Skipped {errs} permission errors."
        )
        self._populate_root()

    # ---- Tree population (lazy) ----
    def _populate_root(self) -> None:
        if not self.tree_root:
            return
        iid = self._insert_node("", self.tree_root)
        # Auto-expand top level
        self._populate_children(iid, self.tree_root)
        self.tree.item(iid, open=True)

    def _insert_node(self, parent_iid: str, node: Node) -> str:
        v = node.verdict or safety.classify(node.path)
        if not self.show[v.category].get():
            return ""
        text = node.name if parent_iid else node.path
        iid = self.tree.insert(
            parent_iid,
            "end",
            text=text,
            values=(human_size(node.size), f"{node.file_count:,}", v.category, v.reason),
            tags=(v.category,),
        )
        self.iid_to_node[iid] = node
        # Insert a placeholder so the chevron appears for non-empty dirs
        if node.children:
            self.tree.insert(iid, "end", text="…", values=("", "", "", ""))
        return iid

    def _populate_children(self, parent_iid: str, node: Node) -> None:
        # Clear placeholder children
        for child_iid in self.tree.get_children(parent_iid):
            if child_iid not in self.iid_to_node:
                self.tree.delete(child_iid)
        # Sort children by size desc
        for child in sorted(node.children, key=lambda c: c.size, reverse=True):
            self._insert_node(parent_iid, child)

    def _on_open(self, _event) -> None:
        iid = self.tree.focus()
        node = self.iid_to_node.get(iid)
        if not node:
            return
        # Only repopulate if this node still has a placeholder
        kids = self.tree.get_children(iid)
        if len(kids) == 1 and kids[0] not in self.iid_to_node:
            self._populate_children(iid, node)

    def _refresh_view(self) -> None:
        if not self.tree_root:
            return
        self.tree.delete(*self.tree.get_children())
        self.iid_to_node.clear()
        self._populate_root()

    def _on_select(self, _event) -> None:
        nodes = [self.iid_to_node[i] for i in self.tree.selection() if i in self.iid_to_node]
        if not nodes:
            self.selected_lbl.set("")
            self.delete_btn.config(state=tk.DISABLED)
            return
        total = sum(n.size for n in nodes)
        any_blocked = any(safety.is_deletion_blocked(n.path) for n in nodes)
        self.selected_lbl.set(f"Selected: {len(nodes)} item(s), {human_size(total)}")
        self.delete_btn.config(state=tk.DISABLED if any_blocked else tk.NORMAL)

    # ---- Deletion ----
    def _delete_selected(self) -> None:
        nodes = [self.iid_to_node[i] for i in self.tree.selection() if i in self.iid_to_node]
        if not nodes:
            return

        # Re-check safety; a NEVER node might have slipped in via multi-select on differing categories
        blocked = [(n.path, safety.is_deletion_blocked(n.path)) for n in nodes if safety.is_deletion_blocked(n.path)]
        if blocked:
            msg = "\n".join(f"• {p} — {r}" for p, r in blocked[:10])
            messagebox.showerror("DiskDoctor — refused", f"Refusing to delete protected paths:\n\n{msg}")
            return

        total = sum(n.size for n in nodes)
        preview = "\n".join(f"• [{(n.verdict or safety.classify(n.path)).category}] {human_size(n.size):>9}  {n.path}" for n in nodes[:15])
        more = f"\n…and {len(nodes) - 15} more" if len(nodes) > 15 else ""
        ok = messagebox.askyesno(
            "Confirm — Recycle Bin",
            f"Send {len(nodes)} item(s), {human_size(total)} total, to the Recycle Bin?\n\n"
            f"{preview}{more}\n\n"
            f"You can restore from Recycle Bin if anything was a mistake.",
            icon="warning",
        )
        if not ok:
            return

        ok_count = 0
        failures: list[str] = []
        for n in nodes:
            success, msg = send_to_recycle_bin(n.path)
            if success:
                ok_count += 1
            else:
                failures.append(f"{n.path}: {msg}")

        summary = f"Recycled {ok_count}/{len(nodes)} item(s)."
        if failures:
            summary += "\n\nFailed:\n" + "\n".join(failures[:10])
        messagebox.showinfo("DiskDoctor", summary)
        self.status.set(summary.split("\n")[0])

        # Mark deleted nodes in the tree (don't auto-rescan — that's expensive)
        for iid in list(self.tree.selection()):
            node = self.iid_to_node.get(iid)
            if node and not os.path.exists(node.path):
                self.tree.item(iid, text=f"[recycled] {node.name or node.path}")


def main() -> None:
    if sys.platform != "win32":
        print("DiskDoctor is Windows-only (uses Recycle Bin via SHFileOperationW).")
        sys.exit(1)
    root = tk.Tk()
    try:
        # Better DPI scaling on Win10/11
        ctypes_user32 = __import__("ctypes").windll.shcore
        ctypes_user32.SetProcessDpiAwareness(1)
    except Exception:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
