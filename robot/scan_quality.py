"""Conservative mapping-only rejection; raw scans remain authoritative for safety."""
import math


def mapping_ranges(ranges,minimum,maximum):
    result=list(ranges);removed=0
    # Reject only isolated FAR returns between two agreeing nearer returns.
    # Never remove a closer isolated obstacle and never turn noise into free space.
    for i in range(1,len(ranges)-1):
        left,value,right=ranges[i-1:i+2]
        if not all(math.isfinite(x) and minimum<=x<=maximum for x in (left,value,right)):continue
        if abs(left-right)<=max(.12,.04*min(left,right)) and value-max(left,right)>max(.5,.2*max(left,right)):
            result[i]=float('nan');removed+=1
    return result,removed


def scan_metrics(msg,now_ns):
    valid=[r for r in msg.ranges if math.isfinite(r) and msg.range_min<=r<=msg.range_max]
    _,outliers=mapping_ranges(msg.ranges,msg.range_min,msg.range_max)
    stamp=msg.header.stamp.sec*10**9+msg.header.stamp.nanosec
    sectors=set(int(((msg.angle_min+i*msg.angle_increment)%(2*math.pi))/(math.pi/6))
                for i,r in enumerate(msg.ranges) if math.isfinite(r) and msg.range_min<=r<=msg.range_max)
    return {'points':len(msg.ranges),'valid_points':len(valid),'covered_sectors':len(sectors),
            'isolated_far_returns':outliers,'stamp_age_s':(now_ns-stamp)/1e9,
            'scan_period_s':msg.scan_time,'ray_span_s':max(0,len(msg.ranges)-1)*msg.time_increment,
            'source_stamp_ns':stamp,'frame_id':msg.header.frame_id,
            'usable':len(valid)>=20 and len(sectors)>=3 and -.2<=(now_ns-stamp)/1e9<1}
