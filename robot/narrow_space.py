"""Conservative straight-step clearance, in base_link metres.

Matches Nav2's 0.40 x 0.30 m footprint, with 0.05 m margin.
Only supports forward translation; no inferred rear clearance or contact recovery.
"""
import math

FRONT, HALF_WIDTH, MARGIN, LASER_X = .20, .15, .05, .103


def forward_step_clear(points, distance=.03):
    if not 0 < distance <= .05 or not points:
        return False
    front, side = FRONT+MARGIN, HALF_WIDTH+MARGIN
    # Includes the present body and the entire swept region. No side obstacle
    # is mistaken for a frontal obstruction outside that rectangle.
    if any(-FRONT-MARGIN <= x <= front+distance and abs(y) <= side for x,y in points):
        return False
    rays = [(math.atan2(y,x-LASER_X), math.hypot(x-LASER_X,y)) for x,y in points]
    # Require measured free rays across the swept leading edge. Missing beams
    # and large gaps are unknown, never clear. Check at 1 cm lateral spacing.
    for i in range(41):
        y = -side+i*.01
        x = front+distance
        angle, length = math.atan2(y,x-LASER_X), math.hypot(x-LASER_X,y)
        near = [(abs(math.atan2(math.sin(a-angle),math.cos(a-angle))),r) for a,r in rays]
        delta, measured = min(near)
        # Bound angular interpolation to 12 mm at the swept edge, within
        # the 50 mm body margin; large unobserved sectors remain blocked.
        if delta > math.radians(4.) or length*math.sin(delta) > .012 or measured < length+.02:
            return False
    return True
