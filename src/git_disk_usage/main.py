#!/usr/bin/env python3
"""Interactive reporter for disk usage and tracked sizes across git repos."""


from __future__ import annotations

import os
import stat
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Footer, Header, Static


EXCLUDED_DIRS = {"__external", "_norepo"}


SortKey = Literal["no", "repo", "branch", "files", "tracked", "usage", "state"]


@dataclass(frozen=True)
class RepoRecord:
    no: int
    repo: str
    branch: str
    files: int
    tracked: int
    usage: int
    state: str


def format_size(num_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(num_bytes)
    for unit in units:
        if abs(value) < 1024.0 or unit == units[-1]:
            return f"{value:,.2f} {unit}"
        value /= 1024.0
    return f"{num_bytes:,} B"


def is_excluded(path: Path, root: Path) -> bool:
    rel_parts = path.relative_to(root).parts
    return any(part in EXCLUDED_DIRS for part in rel_parts)


def find_repos(root: Path) -> list[Path]:
    repos: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        if is_excluded(current, root):
            dirnames[:] = []
            continue

        if ".git" in filenames or ".git" in dirnames:
            repos.append(current)
            dirnames[:] = []
            continue

        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]

    return sorted(repos, key=lambda p: str(p.relative_to(root)))


def current_branch(path: Path) -> str:
    proc = subprocess.run(
        ["git", "-C", str(path), "branch", "--show-current"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return "<unknown>"
    out = proc.stdout.strip()
    return out if out else "<detached>"


def tracked_stats(path: Path) -> tuple[int, int] | None:
    proc = subprocess.run(
        ["git", "-C", str(path), "ls-files", "-z"],
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return None

    total = 0
    files = 0
    for name in proc.stdout.split(b"\0"):
        if not name:
            continue
        rel = name.decode(errors="replace")
        target = path / rel
        try:
            st = target.lstat()
        except OSError:
            continue
        if not (stat.S_ISREG(st.st_mode) or stat.S_ISLNK(st.st_mode)):
            continue
        total += st.st_size
        files += 1
    return total, files


def git_usage_stats(path: Path) -> int:
    """Calculate disk usage in bytes using git rev-list, with count-objects fallback."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(path), "rev-list", "--objects", "--all", "--disk-usage"],
            capture_output=True,
            text=True,
            check=False,
            timeout=3.0,
        )
        if proc.returncode == 0:
            val = proc.stdout.strip()
            if val.isdigit():
                return int(val)
    except (subprocess.TimeoutExpired, OSError):
        pass

    # Fallback to git count-objects -v
    try:
        proc = subprocess.run(
            ["git", "-C", str(path), "count-objects", "-v"],
            capture_output=True,
            text=True,
            check=False,
            timeout=3.0,
        )
        if proc.returncode == 0:
            loose_kib = 0
            pack_kib = 0
            for line in proc.stdout.splitlines():
                if line.startswith("size:"):
                    parts = line.split(":", 1)
                    if len(parts) == 2 and parts[1].strip().isdigit():
                        loose_kib = int(parts[1].strip())
                elif line.startswith("size-pack:"):
                    parts = line.split(":", 1)
                    if len(parts) == 2 and parts[1].strip().isdigit():
                        pack_kib = int(parts[1].strip())
            return (loose_kib + pack_kib) * 1024
    except Exception:
        pass

    return 0


def scan_repositories(
    root: Path,
    on_row: Callable[[RepoRecord, int, int, int], None] | None = None,
) -> tuple[list[RepoRecord], int, int]:
    repos = find_repos(root)
    rows: list[RepoRecord] = []
    checked = 0
    skipped = 0
    total_candidates = len(repos)

    for idx, repo in enumerate(repos, start=1):
        rel = str(repo.relative_to(root))
        stats = tracked_stats(repo)

        if stats is None:
            skipped += 1
            record = RepoRecord(no=idx, repo=rel, branch="-", files=0, tracked=0, usage=0, state="SKIP")
        else:
            checked += 1
            tracked, files = stats
            usage = git_usage_stats(repo)
            record = RepoRecord(
                no=idx,
                repo=rel,
                branch=current_branch(repo),
                files=files,
                tracked=tracked,
                usage=usage,
                state="OK",
            )

        rows.append(record)
        if on_row is not None:
            on_row(record, checked, skipped, total_candidates)

    return rows, checked, skipped


class RepoSizeApp(App[None]):
    """Interactive TUI for git disk usage report."""

    TITLE = "GIT DISK USAGE REPORTER"

    CSS = """
    Screen {
        align: center middle;
        overflow: hidden;
    }

    #header {
        width: 100%;
        padding: 0 1;
    }

    #summary {
        width: 100%;
        padding: 0 1;
    }

    #repo-table {
        height: 1fr;
        width: 100%;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("ctrl+r", "toggle_sort_direction", "Reverse sort"),
        Binding("less_than_sign,comma", "sort_prev", "Previous column"),
        Binding("greater_than_sign,full_stop", "sort_next", "Next column"),
        Binding("ctrl+c", "quit", "Quit"),
    ]

    SORT_KEYS: tuple[SortKey, ...] = ("no", "repo", "branch", "files", "tracked", "usage", "state")
    SORT_LABELS = {
        "no": "NO",
        "repo": "REPO",
        "branch": "BRANCH",
        "files": "FILES",
        "tracked": "TRACKED",
        "usage": "USAGE",
        "state": "STATE",
    }
    TABLE_COLUMNS = {
        "no": ("NO", 6),
        "repo": ("REPO", 30),
        "branch": ("BRANCH", 16),
        "files": ("FILES", 9),
        "tracked": ("TRACKED", 12),
        "usage": ("USAGE", 12),
        "state": ("STATE", 6),
    }
    MIN_REPO_WIDTH = 18
    TABLE_BASE_WIDTH = 1
    VERTICAL_SCROLLBAR_WIDTH = 1

    def __init__(self, root: Path) -> None:
        super().__init__()
        self.root = root
        self.rows: list[RepoRecord] = []
        self.checked = 0
        self.skipped = 0
        self.total_candidates = 0
        self.scan_complete = False
        self.scan_error: str | None = None
        self.sort_index = 0
        self.sort_reverse = False
        self.current_sort_key: SortKey = "usage"

    def compose(self) -> ComposeResult:
        subtitle = f"exclude: {', '.join(sorted(EXCLUDED_DIRS))}"

        yield Header(show_clock=True)
        yield Static(subtitle, id="header")
        yield DataTable(id="repo-table", show_row_labels=False, show_cursor=False, cursor_type="none")
        yield Static("", id="summary")
        yield Footer()

    def on_mount(self) -> None:
        self.current_sort_key = "usage"
        self.sort_reverse = True
        self._refresh_table()
        self.run_worker(self._scan_in_background, thread=True, exclusive=True)

    def _scan_in_background(self) -> None:
        try:
            rows, checked, skipped = scan_repositories(
                self.root,
                on_row=lambda record, row_checked, row_skipped, total: self.call_from_thread(
                    self._accept_scan_row,
                    record,
                    row_checked,
                    row_skipped,
                    total,
                ),
            )
        except Exception as exc:
            self.call_from_thread(self._scan_failed, str(exc))
            return

        self.call_from_thread(self._finish_scan, len(rows), checked, skipped)

    def _accept_scan_row(
        self,
        record: RepoRecord,
        checked: int,
        skipped: int,
        total_candidates: int,
    ) -> None:
        self.rows.append(record)
        self.checked = checked
        self.skipped = skipped
        self.total_candidates = total_candidates
        self._refresh_table()

    def _finish_scan(self, total_candidates: int, checked: int, skipped: int) -> None:
        self.total_candidates = total_candidates
        self.checked = checked
        self.skipped = skipped
        self.scan_complete = True
        self._refresh_table()

    def _scan_failed(self, message: str) -> None:
        self.scan_complete = True
        self.scan_error = message
        self._refresh_table()

    def on_resize(self, event) -> None:
        if self.rows:
            self._refresh_table()

    def _header_text(self, key: str, label: str) -> Text:
        if key == self.current_sort_key:
            return Text(label, style="bold black on yellow")
        return Text(label, style="bold bright_cyan")

    def _column_widths(self, table: DataTable) -> dict[str, int]:
        table_width = max(0, table.size.width)
        if table_width <= 0:
            table_width = max(72, self.size.width)

        row_label_adjust = 0
        overhead = (
            len(self.TABLE_COLUMNS) * table.cell_padding * 2
            + self.TABLE_BASE_WIDTH
            + self.VERTICAL_SCROLLBAR_WIDTH
            + row_label_adjust
        )
        width_budget = max(10, table_width - overhead)

        fixed_keys = ("no", "branch", "files", "tracked", "usage", "state")
        fixed_widths = [self.TABLE_COLUMNS[key][1] for key in fixed_keys]
        fixed_total = sum(fixed_widths)
        available_repo = max(self.MIN_REPO_WIDTH, width_budget - fixed_total)
        repo_label, _ = self.TABLE_COLUMNS["repo"]
        return {
            "no": self.TABLE_COLUMNS["no"][1],
            "repo": max(len(repo_label), available_repo),
            "branch": self.TABLE_COLUMNS["branch"][1],
            "files": self.TABLE_COLUMNS["files"][1],
            "tracked": self.TABLE_COLUMNS["tracked"][1],
            "usage": self.TABLE_COLUMNS["usage"][1],
            "state": self.TABLE_COLUMNS["state"][1],
        }

    def _setup_columns(self, table: DataTable) -> None:
        widths = self._column_widths(table)
        if not table.columns:
            for key, (label, _default_width) in self.TABLE_COLUMNS.items():
                table.add_column(self._header_text(key, label), key=key, width=widths[key])
            return

        for key, (label, _default_width) in self.TABLE_COLUMNS.items():
            column = next(table.get_column(key), None)
            if column is not None:
                column.width = widths[key]
                column.label = self._header_text(key, label)
        table.refresh()

    def _sort_rows(self) -> list[RepoRecord]:
        sort_key = self.current_sort_key

        def key_fn(row: RepoRecord):
            match sort_key:
                case "no":
                    return row.no
                case "repo":
                    return row.repo.lower()
                case "branch":
                    return row.branch.lower()
                case "files":
                    return row.files
                case "tracked":
                    return row.tracked
                case "usage":
                    return row.usage
                case "state":
                    return row.state
                case _:
                    return row.no

        return sorted(self.rows, key=key_fn, reverse=self.sort_reverse)

    def _refresh_table(self) -> None:
        table = self.query_one("#repo-table", DataTable)

        table.clear(columns=True)
        self._setup_columns(table)

        sorted_rows = self._sort_rows()

        for row in sorted_rows:
            row_style = "green" if row.state == "OK" else "yellow"

            table.add_row(
                Text(f"{row.no:>6}", style=row_style),
                Text(row.repo, style=row_style),
                Text(row.branch, style=row_style),
                Text(f"{row.files:,}", style=row_style),
                Text(format_size(row.tracked), style=row_style),
                Text(format_size(row.usage), style=row_style),
                Text(row.state, style=row_style),
            )

        sort_label = self.SORT_LABELS[self.current_sort_key]
        direction = "DESC" if self.sort_reverse else "ASC"
        total_tracked = format_size(sum(row.tracked for row in self.rows if row.state == "OK"))
        total_usage = format_size(sum(row.usage for row in self.rows if row.state == "OK"))
        candidate_count = self.total_candidates or len(self.rows)
        scan_status = "complete" if self.scan_complete else "scanning"
        if self.scan_error is not None:
            scan_status = f"error: {self.scan_error}"

        self.query_one("#header", Static).update(
            f"exclude: {', '.join(sorted(EXCLUDED_DIRS))} | "
            f"candidates={candidate_count} | scanned={len(self.rows)} | "
            f"total tracked: {total_tracked} | total usage: {total_usage} | {scan_status}"
        )
        self.query_one("#summary", Static).update(
            f"Sorted by: {sort_label} ({direction}) | "
            f"checked: {self.checked}, skipped: {self.skipped}"
        )

    def action_sort_prev(self) -> None:
        current_key_index = self.SORT_KEYS.index(self.current_sort_key)
        next_key_index = (current_key_index - 1) % len(self.SORT_KEYS)
        target = self.SORT_KEYS[next_key_index]
        self.current_sort_key = target
        self.sort_reverse = target in {"files", "tracked", "usage"}
        self._refresh_table()

    def action_sort_next(self) -> None:
        current_key_index = self.SORT_KEYS.index(self.current_sort_key)
        next_key_index = (current_key_index + 1) % len(self.SORT_KEYS)
        target = self.SORT_KEYS[next_key_index]
        self.current_sort_key = target
        self.sort_reverse = target in {"files", "tracked", "usage"}
        self._refresh_table()

    def action_toggle_sort_direction(self) -> None:
        self.sort_reverse = not self.sort_reverse
        self._refresh_table()

    def action_quit(self) -> None:
        self.exit()


def main() -> int:
    app = RepoSizeApp(Path.cwd())
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
