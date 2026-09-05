#!/usr/bin/env python3
"""Generate a realistic TUI screenshot for git-disk-usage documentation."""

import asyncio
from pathlib import Path
import subprocess

from git_disk_usage.main import RepoSizeApp, RepoRecord

FAKE_RECORDS = [
    RepoRecord(1, "source/repos/linux-kernel", "master", 84210, 1540000000, 4820000000, "OK"),
    RepoRecord(2, "source/repos/cpython", "main", 5120, 185400000, 892000000, "OK"),
    RepoRecord(3, "source/repos/neovim", "master", 2840, 42100000, 312000000, "OK"),
    RepoRecord(4, "source/repos/frontend-webapp", "main", 3210, 68900000, 245000000, "OK"),
    RepoRecord(5, "source/repos/game-engine", "main", 1420, 48200000, 182000000, "OK"),
    RepoRecord(6, "source/repos/ripgrep", "master", 145, 8900000, 124000000, "OK"),
    RepoRecord(7, "source/repos/textual", "main", 620, 24500000, 95000000, "OK"),
    RepoRecord(8, "source/repos/backend-service", "feature/auth", 412, 12800000, 48200000, "OK"),
    RepoRecord(9, "source/repos/docs-site", "develop", 185, 4100000, 15300000, "OK"),
    RepoRecord(10, "source/repos/dotfiles", "main", 78, 1250000, 5600000, "OK"),
    RepoRecord(11, "source/repos/infra-terraform", "main", 64, 850000, 3200000, "OK"),
    RepoRecord(12, "source/repos/broken-repo", "-", 0, 0, 0, "SKIP"),
]

class MockScreenshotApp(RepoSizeApp):
    def on_mount(self) -> None:
        self.current_sort_key = "usage"
        self.sort_reverse = True
        self.rows = list(FAKE_RECORDS)
        self.checked = sum(1 for r in FAKE_RECORDS if r.state == "OK")
        self.skipped = sum(1 for r in FAKE_RECORDS if r.state == "SKIP")
        self.total_candidates = len(FAKE_RECORDS)
        self.scan_complete = True
        self._refresh_table()

    def _scan_in_background(self) -> None:
        pass

async def main():
    assets_dir = Path("assets")
    assets_dir.mkdir(parents=True, exist_ok=True)
    svg_path = assets_dir / "screenshot.svg"
    png_path = assets_dir / "screenshot.png"

    app = MockScreenshotApp(Path.cwd())
    async with app.run_test(size=(110, 23)) as pilot:
        await pilot.pause()
        svg_content = app.export_screenshot(title="git-disk-usage")
        svg_path.write_text(svg_content, encoding="utf-8")
        print(f"Saved {svg_path}")

    # Convert to high-resolution PNG using rsvg-convert (2x scale for Retina)
    subprocess.run(
        ["rsvg-convert", "-f", "png", "-z", "2", "-o", str(png_path), str(svg_path)],
        check=True,
    )
    print(f"Saved {png_path}")

if __name__ == "__main__":
    asyncio.run(main())
