"""Geometry and recorded-route handling, independent of ROS."""
import math
from collections import deque


def wrap(angle):
    return math.atan2(math.sin(angle), math.cos(angle))


def map_file_pixels(data):
    # With YAML free_thresh=.25 / occupied_thresh=.65, gray 128 reloads as
    # unknown. Gray 205 would reload as FREE and must not represent unknown.
    return bytes(128 if v < 0 or 25 < v < 65 else 254 if v <= 25 else 0 for v in data)


def transform_pose(pose, transform):
    x, y, yaw = pose
    tx, ty, theta = transform
    c, s = math.cos(theta), math.sin(theta)
    return [tx + c*x - s*y, ty + s*x + c*y, wrap(yaw + theta)]


def validate_goal(grid, x, y, radius=0.23):
    if not all(math.isfinite(v) for v in (x, y)):
        raise ValueError('Target coordinates must be finite')
    ox, oy, theta = grid['origin']
    c, s = math.cos(theta), math.sin(theta)
    dx, dy = x-ox, y-oy
    gx, gy = (c*dx+s*dy)/grid['resolution'], (-s*dx+c*dy)/grid['resolution']
    r = radius/grid['resolution']
    width, height = grid['width'], grid['height']
    # Include the robot footprint, not just the clicked pixel.
    for cy in range(math.floor(gy-r), math.ceil(gy+r)+1):
        for cx in range(math.floor(gx-r), math.ceil(gx+r)+1):
            if math.hypot(cx+.5-gx, cy+.5-gy) > r+.71:
                continue
            if not (0 <= cx < width and 0 <= cy < height):
                raise ValueError('Target is outside the mapped free area')
            value = grid['data'][cy*width+cx]
            if value < 0:
                raise ValueError('Goal is too close to unknown space for the robot footprint. Explore more or choose a point farther inside free space.')
            if value > 25:
                raise ValueError('Target is too close to an obstacle')


def safe_cells(grid, radius=.23):
    """Disk erosion of known free space, matching validate_goal at cell centers.

    Row prefix sums avoid an O(cells * footprint area) scan. Outside the map
    counts as occupied. Called in the exploration worker, never the ROS timer.
    """
    w, h, data = grid['width'], grid['height'], grid['data']
    r = radius/grid['resolution'] + .71
    extent = math.floor(r)
    rows = []
    for y in range(h):
        row = [0]
        for v in data[y*w:(y+1)*w]:
            row.append(row[-1] + (not 0 <= v <= 25))
        rows.append(row)
    safe = bytearray(w*h)
    spans = [(dy, math.floor(math.sqrt(r*r-dy*dy))) for dy in range(-extent, extent+1)]
    for y in range(extent, h-extent):
        for x in range(extent, w-extent):
            if all(rows[y+dy][x+dx+1] == rows[y+dy][x-dx] for dy, dx in spans):
                safe[y*w+x] = 1
    return safe


def exploration_targets(grid, pose, visited=(), max_distance=1.5):
    """Reachable footprint-safe viewing points near free/unknown boundaries.

    No frontier is a license to enter unknown space. Nav2 must still plan and
    collision-check the route. A missing safe seed requires operator relocation.
    """
    w, h, res, data = grid['width'], grid['height'], grid['resolution'], grid['data']
    ox, oy, theta = grid['origin']
    c, s = math.cos(theta), math.sin(theta)
    dx, dy = pose[0]-ox, pose[1]-oy
    gx, gy = (c*dx+s*dy)/res, (-s*dx+c*dy)/res
    safe = safe_cells(grid)
    seeds = [(math.hypot(x+.5-gx, y+.5-gy), y*w+x)
             for y in range(max(0, int(gy)-5), min(h, int(gy)+6))
             for x in range(max(0, int(gx)-5), min(w, int(gx)+6)) if safe[y*w+x]]
    if not seeds:
        return []
    distance, seed = min(seeds)
    if distance*res > .25:
        return []
    # Breadth-first reachability on the inflated free area. No diagonal cuts.
    queue = deque([(seed, 0)])
    seen = {seed}
    reachable = []
    while queue:
        i, steps = queue.popleft()
        reachable.append((i, steps*res))
        if steps*res > max_distance:
            continue
        x, y = i % w, i // w
        for nx, ny in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
            j = ny*w+nx
            if 0 <= nx < w and 0 <= ny < h and safe[j] and j not in seen:
                seen.add(j)
                queue.append((j, steps+1))
    # Only free cells adjacent to unknown count as frontiers, never walls.
    frontiers = []
    for y in range(1,h-1):
        for x in range(1,w-1):
            i = y*w+x
            if 0 <= data[i] <= 25 and any(data[j] < 0 for j in (i-1,i+1,i-w,i+w)):
                frontiers.append((x+.5,y+.5))
    candidates = []
    stride = max(1, round(.12/res))
    for i, travel in reachable:
        x, y = i % w, i // w
        if x % stride or y % stride or travel > max_distance:
            continue
        lx, ly = (x+.5)*res, (y+.5)*res
        wx, wy = ox+c*lx-s*ly, oy+s*lx+c*ly
        if math.hypot(wx-pose[0], wy-pose[1]) < .30:
            continue
        if any(math.hypot(wx-p[0], wy-p[1]) < .35 for p in visited):
            continue
        nearby = [(fx,fy) for fx,fy in frontiers if math.hypot(fx-x-.5,fy-y-.5)*res <= .65]
        if len(nearby) < 3:
            continue
        fx, fy = min(nearby, key=lambda f: math.hypot(f[0]-x-.5,f[1]-y-.5))
        heading = wrap(math.atan2(fy-y-.5,fx-x-.5)+theta)
        score = travel + .15*abs(wrap(heading-pose[2])) - min(.4, len(nearby)*res*.04)
        candidates.append((score, [wx,wy,heading]))
    candidates.sort(key=lambda p:p[0])
    return [p for _,p in candidates[:30]]


class Trail:
    def __init__(self):
        self.points = []

    def reset(self, pose):
        self.points = [list(pose)]

    def append(self, pose, force=False):
        if not self.points:
            self.reset(pose)
        else:
            previous = self.points[-1]
            if force or math.hypot(pose[0]-previous[0], pose[1]-previous[1]) >= .025 or abs(wrap(pose[2]-previous[2])) >= .1:
                self.points.append(list(pose))

    @property
    def length(self):
        return sum(math.hypot(b[0]-a[0], b[1]-a[1]) for a, b in zip(self.points, self.points[1:]))

    def returning(self, current, reverse):
        if self.length < .06:
            raise ValueError('No recorded trip to return along yet')
        end = self.points[-1]
        if math.hypot(current[0]-end[0], current[1]-end[1]) > .2:
            raise ValueError('Robot moved away from the recorded route; start a new trip')
        points = [list(current)]
        for p in reversed(self.points):
            if math.hypot(p[0]-points[-1][0], p[1]-points[-1][1]) >= .005:
                points.append(list(p))
        if len(points) < 2:
            raise ValueError('Recorded route is too short')
        if not reverse:
            for a, b in zip(points, points[1:]):
                a[2] = math.atan2(b[1]-a[1], b[0]-a[0])
            points[-1][2] = points[-2][2]
        return points
