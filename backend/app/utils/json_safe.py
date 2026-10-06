"""
Recursively converts date/datetime/Decimal objects to strings so dicts can
be safely stored in SQLite/Postgres JSON columns. Several modules (recurring
detection, simulation, anomaly reasons) build dicts that mix computed floats
with real date objects — this is the one place that sanitizes them before
they hit the DB, rather than scattering str() calls across every call site.
"""
from datetime import date, datetime
from decimal import Decimal
import numpy as np


def to_jsonable(obj):
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return [to_jsonable(v) for v in obj.tolist()]
    return obj
