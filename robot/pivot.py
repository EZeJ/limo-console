"""Small, bounded differential pivots; linear velocity is always exactly zero."""
import math

def rotation_clear(points,angle,half_length=.22,half_width=.17):
    if not points:return False
    # A half-turn already sweeps the entire disk of this symmetric footprint.
    if abs(angle)>=math.pi:
        radius2=half_length**2+half_width**2
        return all(x*x+y*y>radius2 for x,y in points)
    # Match Nav2's 0.40 x 0.30 m footprint plus 0.02 m padding.
    for step in range(max(2,math.ceil(abs(angle)/.02))+1):
        theta=angle*step/max(2,math.ceil(abs(angle)/.02));c,s=math.cos(theta),math.sin(theta)
        for x,y in points:
            if abs(c*x+s*y)<=half_length and abs(-s*x+c*y)<=half_width:return False
    return True

class Pivot:
    def __init__(self,yaw,now,angle=.35,speed=.18):
        self.last_yaw=yaw;self.angle=angle;self.progress=0.;self.speed=math.copysign(speed,angle)
        self.deadline=now+abs(angle)/speed+3
    def command(self,yaw,now):
        delta=math.atan2(math.sin(yaw-self.last_yaw),math.cos(yaw-self.last_yaw))
        self.last_yaw=yaw;self.progress+=delta
        if abs(self.progress)>=abs(self.angle):return (0.,0.),True
        if now>self.deadline:raise ValueError('In-place scan turn timed out')
        return (0.,self.speed),False
    @property
    def remaining(self):return self.angle-self.progress
