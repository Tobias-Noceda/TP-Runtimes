# How many distinct Sokoban states share a hash: state = (player, (box, box)),
# all placements on a WxH grid. With protopy's old tuple hash (h*1000003 ^ eh)
# swapping elements across nesting levels cancelled out, so e.g. player/box
# swaps collided and, since protopy's dict/set treated tuple hashes as exact,
# distinct states were merged. Prints one JSON line.
# Usage: hash_collisions.py [width] [height]
import json
import sys
from itertools import combinations

W = int(sys.argv[1]) if len(sys.argv) > 1 else 6
H = int(sys.argv[2]) if len(sys.argv) > 2 else 6
cells = [(x, y) for x in range(W) for y in range(H)]

states = [(p, (a, b)) for p in cells for a, b in combinations(cells, 2) if p not in (a, b)]
hashes = {}
for s in states:
    hashes.setdefault(hash(s), []).append(s)
colliding = sum(len(v) for v in hashes.values() if len(v) > 1)
as_set = len(set(states))  # what a set/dict keyed by state keeps

example = next((v[:2] for v in hashes.values() if len(v) > 1), None)
print(json.dumps({
    "runtime": f"{sys.implementation.name} {sys.version.split()[0]}",
    "states": len(states),
    "distinct_hashes": len(hashes),
    "states_in_colliding_buckets": colliding,
    "set_size": as_set,
    "states_lost_by_set": len(states) - as_set,
    "example_collision": repr(example),
}))
