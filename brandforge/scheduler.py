"""Weekly content calendar: one slot per approved post, weekdays only, best-time defaults."""
from datetime import datetime, time, timedelta

SLOTS = {"LinkedIn": time(9, 0), "X": time(12, 0), "Instagram": time(19, 0)}


def nth_weekday(start, n):
    d, seen = start, -1
    while True:
        if d.weekday() < 5:
            seen += 1
            if seen == n:
                return d
        d += timedelta(days=1)


def slot_for(platform, n_already_scheduled, start):
    """n-th approved post on a platform goes on the n-th weekday from `start`."""
    return datetime.combine(nth_weekday(start, n_already_scheduled), SLOTS.get(platform, time(10, 0)))
