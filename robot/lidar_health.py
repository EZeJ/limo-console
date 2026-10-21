"""Read-only scan health. No persistent pause or motor-control operation."""
class LidarHealth:
    busy=False
    def __init__(self):self.age=float('inf')
    def tick(self,age):self.age=age
    def snapshot(self):
        online=self.age<1
        return dict(state='running' if online else 'offline',busy=False,available=online,
                    message='Lidar is scanning' if online else 'No scan data',
                    control_available=False)
    def require_scanning(self):
        if self.age>=1:raise ValueError('Fresh lidar scans are required')
