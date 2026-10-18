"""Private operator helper. Do not run full inventories in public Actions logs."""
import json
from pathlib import Path
import sys


def normalize(records):
    result = {}
    for item in records:
        key = item['name'].lower() + '|' + item['type'].upper()
        if key in result:
            raise ValueError('Duplicate RRset identity')
        result[key] = (int(item['ttl']), tuple(sorted(item['rrdatas'])))
    return result


def differences(old, new):
    return {key for key in old.keys() | new.keys() if old.get(key) != new.get(key)}


if __name__ == '__main__':
    old, new = [normalize(json.loads(Path(p).read_text())) for p in sys.argv[1:3]]
    expected = set(json.loads(Path(sys.argv[3]).read_text()))
    changed = differences(old, new)
    unexpected, missing = changed - expected, expected - changed
    if unexpected or missing:
        print(json.dumps({'unapproved_differences': sorted(unexpected), 'approved_but_unchanged': sorted(missing)}, indent=2))
        sys.exit(1)
    print('Complete provided exports match except for the exact approved RRset differences.')
