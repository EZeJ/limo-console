"""Persistent manual speed limits; angular range is an app setting, not a rating."""
import json
import math
from pathlib import Path

DEFAULTS = {'forward': .10, 'reverse': .05, 'angular': .30}
RATED_MAX = 1.0
ANGULAR_MAX = 2.0


def validate_limits(forward, reverse, angular=DEFAULTS['angular']):
    result = {}
    for name, value in (('forward', forward), ('reverse', reverse)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError('Speed must be a number in m/s.')
        value = float(value)
        if not math.isfinite(value) or not 0 <= value <= RATED_MAX:
            raise ValueError('Forward and reverse limits must be between 0 and 1.0 m/s.')
        result[name] = value
    if isinstance(angular, bool) or not isinstance(angular, (int, float)):
        raise ValueError('Turning speed must be a number in rad/s.')
    angular = float(angular)
    if not math.isfinite(angular) or not 0 <= angular <= ANGULAR_MAX:
        raise ValueError('Turning speed must be between 0 and 2.00 rad/s.')
    result['angular'] = angular
    return result


def load_limits(path):
    try:
        data = json.loads(Path(path).read_text())
        return validate_limits(data['forward'], data['reverse'], data.get('angular', DEFAULTS['angular']))
    except (OSError, ValueError, KeyError, TypeError):
        return dict(DEFAULTS)


def save_limits(path, forward, reverse, angular=DEFAULTS['angular']):
    limits = validate_limits(forward, reverse, angular)
    path = Path(path)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(limits)+'\n')
    temporary.replace(path)
    return limits
