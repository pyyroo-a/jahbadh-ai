"""The daily cap on live actions, shared by everyone and kept on disk so a restart doesn't reset it.

The file is {"day": "YYYY-MM-DD", "used": n} in UTC days. A missing file means nothing has been used today. A
file that can't be read or doesn't make sense counts as the cap reached: live mode costs money, so it fails closed.
"""

import json
import logging
import os
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path


def utc_today() -> date:
    return datetime.now(UTC).date()


class DailyLimit:
    def __init__(self, path: Path, per_day: int, today: Callable[[], date] = utc_today):
        self.path, self.per_day, self.today = Path(path), per_day, today

    def _used(self) -> int:
        if not self.path.exists():
            return 0
        try:
            saved = json.loads(self.path.read_text(encoding="utf-8"))
            day, used = saved["day"], saved["used"]
            if not isinstance(day, str) or not isinstance(used, int) or isinstance(used, bool) or used < 0:
                raise ValueError(saved)
        except (OSError, ValueError, KeyError, TypeError):
            logging.getLogger(__name__).warning("Live counter file %s can't be read, so live mode stays closed today",
                                                self.path)
            return self.per_day
        return used if day == self.today().isoformat() else 0

    def remaining(self) -> int:
        return max(0, self.per_day - self._used())

    def take(self) -> bool:
        used = self._used()
        if used >= self.per_day:
            return False
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"day": self.today().isoformat(), "used": used + 1}), encoding="utf-8")
            os.replace(tmp, self.path)                 # a crash mid-write never leaves half a file
        except OSError:
            return False
        return True
