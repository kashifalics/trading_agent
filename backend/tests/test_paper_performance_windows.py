from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.paper.stats import performance_windows


def test_performance_windows_use_closed_time_and_exact_rolling_counts():
    now = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)
    trades = [
        SimpleNamespace(
            id=i + 1,
            closed_at=now - timedelta(days=119 - i, hours=1),
            r_net=2.0 if (i + 1) % 3 == 0 else -1.0,
            exit_reason="target" if (i + 1) % 3 == 0 else "stop",
            mfe_r=1.5 if (i + 1) % 3 == 0 else 0.5,
            mae_r=-0.2 if (i + 1) % 3 == 0 else -1.0,
        )
        for i in range(120)
    ]

    windows = performance_windows(trades, now)

    assert windows["lifetime"]["n_trades"] == 120
    assert windows["last_100"]["n_trades"] == 100
    assert windows["last_100"]["start_at"] == trades[20].closed_at
    assert windows["last_50"]["n_trades"] == 50
    assert windows["last_30_days"]["n_trades"] == 30
    assert windows["last_7_days"]["n_trades"] == 7
    assert windows["last_100"]["target_hits"] == 34
    assert windows["last_100"]["stop_exits"] == 66
    assert windows["last_100"]["longest_losing_streak"] == 2
    assert windows["last_100"]["stopped_mfe_at_least_1r"] == 0
    assert windows["last_100"]["average_mfe_r"] is not None


def test_empty_performance_windows_report_zero_sample_and_undefined_rates():
    now = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)

    windows = performance_windows([], now)

    assert windows["lifetime"]["n_trades"] == 0
    assert windows["last_100"]["tp1_hit_rate"] is None
    assert windows["last_7_days"]["stop_rate"] is None
