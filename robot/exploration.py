"""Bounded frontier exploration; route execution and obstacle avoidance use Nav2."""
import math
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

from PIL import Image
from nav2_msgs.action import NavigateToPose, ComputePathToPose
from action_msgs.msg import GoalStatus
from navigation_core import exploration_targets, transform_pose, validate_goal, map_file_pixels, wrap
from pivot import Pivot,rotation_clear


class Explorer:
    def __init__(self, navigation):
        self.nav = navigation
        self.active = False
        self.started = 0.
        self.reached = 0
        self.visited = []
        self.worker = False
        self.selection = None
        self.next_at = 0.
        self.blocked_since = None
        self.saved_map = None
        self.save_message = ''
        self.max_seconds = 120.
        self.max_distance = 6.
        self.max_speed = .15
        self.planning = False
        self.plan_handle = None
        self.plan_deadline = 0.
        self.plan_attempt = 0
        self.planned_goal = None
        self.failed_targets = []
        self.leg_target_odom = None
        self.failures = 0
        self.consecutive_failures = 0
        self.obstacle_hold = False
        self.cancel_pending = False
        self.hold_deadline = 0.
        self.clear_since = None
        self.scanning = False
        self.scan_attempted = False
        self.stepping = False
        self.step_count = 0
        self.wait_revision = None
        self.scan_turn=None
        self.scan_headings=[]
        self.scan_only=False

    def start(self,max_seconds=120.,max_distance=6.,max_speed=.15):
        n = self.nav
        values=[float(max_seconds),float(max_distance),float(max_speed)]
        if not all(math.isfinite(v) for v in values) or not (5<=values[0]<=300 and .1<=values[1]<=10 and .03<=values[2]<=.5):
            raise ValueError('Exploration limits must be 5–300 s, 0.1–10 m and 0.03–0.5 m/s')
        n.check_ready()
        if not n.planner.server_is_ready():
            raise ValueError('Path planning service is not ready')
        self.active = True
        self.max_seconds,self.max_distance,self.max_speed=values
        self.scanning = self.scan_attempted = False
        self.scan_only=False
        self.stepping = False
        self.step_count = 0
        self.wait_revision = None
        self.scan_turn=None
        self.scan_headings=[n.odom_pose()[2]]
        self.started = time.monotonic()
        self.reached = 0
        self.visited = []
        self.failed_targets = []
        self.leg_target_odom = None
        self.failures = 0
        self.consecutive_failures = 0
        self.obstacle_hold = False
        self.cancel_pending = False
        self.clear_since = None
        self.selection = None
        self.planned_goal = None
        self.planning = False
        self.next_at = self.started
        self.blocked_since = None
        self.saved_map = None
        self.save_message = ''
        n.trail.reset(n.odom_pose())
        n.recording = True
        n.target, n.plan, n.return_mode = None, [], None
        n.mission = uuid.uuid4().hex
        n.last_heartbeat = self.started
        n.phase = 'exploring'
        n.message = 'Exploration: looking for reachable frontiers…'

    def start_scan(self):
        self.start(max_seconds=50,max_distance=.1,max_speed=.05)
        self.scan_only=True
        if not self.try_pivot(full=True):
            self.nav.stop('No clear rotation sweep. Robot stopped.','failed')
            raise ValueError('No clear rotation sweep. Robot stopped.')

    def try_pivot(self,full=False):
        n=self.nav
        if len(self.scan_headings)>=13:return False
        yaw=n.odom_pose()[2]
        for angle in ((2*math.pi,-2*math.pi) if full else (.35,-.35)):
            target=wrap(yaw+angle)
            if not full and any(abs(wrap(target-old))<.20 for old in self.scan_headings):continue
            if not rotation_clear(n.node.lidar_points,angle):continue
            self.scanning=True;self.scan_turn=Pivot(yaw,time.monotonic(),angle)
            self.scan_origin=n.odom_pose();self.scan_map_revision=n.content_revision
            self.scan_headings.append(target)
            n.node.gate.arm('navigation',n.last_heartbeat)
            n.node.gate.pivot_active=True
            n.message='Scanning in place: linear speed is zero. Turning briefly, then stopping to replan.'
            if full:n.message='Scanning in place: linear speed is zero. Completing a 360° lidar sweep.'
            return True
        return False

    def finish_leg(self, status):
        n = self.nav
        n.node.gate.stop()
        n.handle = None
        if self.obstacle_hold and status == GoalStatus.STATUS_CANCELED:
            self.cancel_pending = False
            return
        self.obstacle_hold = self.cancel_pending = False
        if status != GoalStatus.STATUS_SUCCEEDED:
            # An external cancel is terminal. Only a completed Nav2 abort can
            # trigger another goal; STOP/lease/hardware failures clear active.
            if status != GoalStatus.STATUS_ABORTED:
                n.stop('Exploration cancelled. Robot stopped.', 'cancelled')
                return
            self.failures += 1
            self.consecutive_failures += 1
            if self.leg_target_odom is not None:
                self.failed_targets.append(self.leg_target_odom)
            if self.consecutive_failures >= 3 or self.failures >= 6:
                n.stop('Several targets were unreachable. Stopped and requested a map save. Check the surrounding routes.', 'failed')
                return
            self.selection = None
            self.planned_goal = None
            self.blocked_since = None
            n.target, n.plan = None, []
            n.phase = 'exploring'
            n.message = 'Exploration path is no longer valid. Stopped; updating the map and selecting another target.'
            self.next_at = time.monotonic()+2.5
            return
        self.wait_revision = n.content_revision
        self.map_deadline = time.monotonic()+8
        self.consecutive_failures = 0
        self.reached += 1
        self.visited.append(n.odom_pose())  # odom survives SLAM map corrections
        n.phase = 'exploring'
        n.message = 'Target reached. Updating the map and selecting the next target…'
        self.next_at = time.monotonic()+2.5

    def tick(self):
        n = self.nav
        now = time.monotonic()
        if now-self.started >= self.max_seconds or n.trail.length >= self.max_distance or self.reached >= 12:
            n.stop('Exploration time or distance limit reached. Map retained; start another run to continue.', 'complete')
            return
        if self.scanning:
            pose=n.odom_pose()
            if n.node.gate.mode!='navigation' or math.hypot(pose[0]-self.scan_origin[0],pose[1]-self.scan_origin[1])>.03:
                n.stop('In-place scan turn deviated from its position. Stopped.','failed');return
            if not rotation_clear(n.node.lidar_points,self.scan_turn.remaining):
                n.stop('Obstacle inside the rotation sweep. In-place turn stopped.','failed');return
            n.node.gate.pivot_clear=True
            command,done=self.scan_turn.command(pose[2],now)
            if done:
                n.node.gate.stop();self.scanning=False;self.selection=None
                if self.scan_only:
                    n.stop('360° lidar scan complete. Robot stopped.','complete');return
                self.wait_revision=self.scan_map_revision;self.map_deadline=now+8;self.next_at=now+1
                n.message='In-place scan complete. Waiting for map updates before replanning.'
            else:
                n.node.gate.lease=n.last_heartbeat;n.node.gate.receive(*command,now)
            return
        if n.phase != 'exploring':
            blocked = n.node.reason in ('Obstacle close to chassis', 'No usable front lidar returns', 'No usable rear lidar returns')
            self.blocked_since = (self.blocked_since or now) if blocked else None
            if self.blocked_since and now-self.blocked_since > 2:
                n.node.gate.stop()
                self.obstacle_hold = self.cancel_pending = True
                self.hold_deadline = now+15
                self.plan_deadline = now+3
                self.clear_since = None
                n.phase = 'exploring'
                n.message = 'Obstacle pause: stopped, waiting up to 15 seconds for clearance. Stop is always available.'
                try:
                    if n.handle is None:
                        raise RuntimeError('No active route to cancel')
                    n.handle.cancel_goal_async()
                except Exception:
                    n.stop('Could not confirm cancellation of the previous route. Exploration stopped.', 'failed')
            return
        if self.obstacle_hold:
            if self.cancel_pending:
                if now > self.plan_deadline:
                    n.stop('Previous route cancellation timed out. Exploration stopped.', 'failed')
                return
            if now > self.hold_deadline:
                n.stop('Clearance remains blocked. Stopped and requested a map save. Clear nearby obstacles before retrying.', 'failed')
                return
            front, rear, closest = n.node.clearance
            clear = front > .4 and closest > .3
            self.clear_since = (self.clear_since or now) if clear else None
            if self.clear_since and now-self.clear_since >= 1.5:
                # Treat this blocked endpoint like an aborted route, with the
                # same bounded retry count and fresh-map preflight.
                self.obstacle_hold = False
                self.finish_leg(GoalStatus.STATUS_ABORTED)
            return
        if self.wait_revision is not None:
            if n.content_revision <= self.wait_revision:
                if now > self.map_deadline:
                    n.stop('Map did not change after reaching the target. Stopped; inspect scan and localization health.', 'failed')
                return
            self.wait_revision = None
        if self.planning:
            if now > self.plan_deadline:
                n.stop('Path precheck timed out. Stopped.', 'failed')
            return
        if self.planned_goal is not None:
            p, self.planned_goal = self.planned_goal, None
            try:
                validate_goal(n.grid, p[0], p[1])
            except ValueError:
                return
            n.target, n.plan = p[:2], []
            tx, ty, theta = n.transform()
            c, s = math.cos(theta), math.sin(theta)
            self.leg_target_odom = transform_pose(p, [-c*tx-s*ty, s*tx-c*ty, -theta])
            goal = NavigateToPose.Goal()
            goal.pose = n.pose_message(p)
            goal.behavior_tree = '/control/navigate.xml'
            self.selection = None
            n.send(n.goto, goal, 'navigating')
            return
        if self.worker:
            if now > self.next_at:
                n.stop('Frontier calculation timed out. Stopped.', 'failed')
            return
        if now < self.next_at:
            return
        if self.selection is not None:
            while self.selection:
                p = self.selection.pop(0)
                try:
                    validate_goal(n.grid, p[0], p[1])
                except ValueError:
                    continue
                self.check_path(p)
                return
            if self.try_pivot():return
            n.stop('No reachable frontier or clear rotation sweep. Stopped.', 'failed')
            return
        transform = n.transform()
        pose = transform_pose(n.odom_pose(), transform)
        visited = [transform_pose(p, transform) for p in self.visited+self.failed_targets]
        grid, token = n.grid, n.mission
        self.worker = True
        self.next_at = now+10  # fail closed if selection stalls
        def select():
            try:
                candidates = exploration_targets(grid, pose, visited)
                error = None
            except Exception as exc:
                candidates, error = [], str(exc)
            with n.node.lock:
                self.worker = False
                if not self.active or n.mission != token:
                    return
                if error:
                    n.stop('Frontier calculation failed: '+error, 'failed')
                else:
                    if not candidates:
                        if self.try_pivot():return
                        n.stop('No reachable frontier or clear rotation sweep. Stopped.', 'failed')
                        return
                    self.selection = candidates
                    self.next_at = time.monotonic()
        threading.Thread(target=select, daemon=True).start()

    def check_path(self, pose):
        """Preflight candidates without arming motion; skip unreachable targets."""
        n = self.nav
        token = n.mission
        self.plan_attempt += 1
        attempt = self.plan_attempt
        self.planning = True
        self.plan_deadline = time.monotonic()+8
        n.message = 'Exploration: checking paths to candidate targets…'
        goal = ComputePathToPose.Goal()
        goal.goal = n.pose_message(pose)
        goal.planner_id = 'GridBased'
        def current():
            return self.active and n.mission == token and self.plan_attempt == attempt
        def result(f):
            with n.node.lock:
                if not current():
                    return
                self.planning = False
                self.plan_handle = None
                try:
                    answer = f.result()
                    path = answer.result.path.poses
                    if answer.status == GoalStatus.STATUS_SUCCEEDED and path:
                        end = path[-1].pose.position
                        if math.hypot(end.x-pose[0],end.y-pose[1]) <= .10:
                            self.planned_goal = pose
                except Exception:
                    pass  # try the next candidate, still disarmed
        def accepted(f):
            with n.node.lock:
                try:
                    handle = f.result()
                    if not current():
                        if handle.accepted:
                            handle.cancel_goal_async()
                        return
                    if not handle.accepted:
                        self.planning = False
                        return
                    self.plan_handle = handle
                    handle.get_result_async().add_done_callback(result)
                except Exception as exc:
                    if current():
                        n.stop('Path check failed: '+str(exc), 'failed')
        try:
            n.planner.send_goal_async(goal).add_done_callback(accepted)
        except Exception as exc:
            n.stop('Path check failed: '+str(exc), 'failed')

    def stop(self):
        if not self.active:
            return
        self.active = False
        self.scanning = False
        self.stepping = False
        self.obstacle_hold = self.cancel_pending = False
        self.selection = None
        self.planned_goal = None
        self.planning = False
        if self.plan_handle is not None:
            try:
                self.plan_handle.cancel_goal_async()
            except Exception:
                pass
            self.plan_handle = None
        grid = self.nav.grid
        if not grid:
            return
        self.save_message = 'Saving map…'
        def save():
            try:
                # Nav2 map format, separate from the display palette.
                name = 'tour_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')
                folder = Path('/control/maps')
                folder.mkdir(exist_ok=True)
                pixels = map_file_pixels(grid['data'])
                img = Image.frombytes('L', (grid['width'], grid['height']), pixels).transpose(Image.FLIP_TOP_BOTTOM)
                img.save(str(folder/(name+'.pgm')))
                (folder/(name+'.yaml')).write_text(
                    'image: '+name+'.pgm\nmode: trinary\nresolution: '+str(grid['resolution'])+
                    '\norigin: '+str(grid['origin'])+'\nnegate: 0\noccupied_thresh: 0.65\nfree_thresh: 0.25\n')
                message = 'Saved map: '+name
            except Exception as exc:
                name, message = None, 'Save failed: '+str(exc)
            with self.nav.node.lock:
                self.saved_map, self.save_message = name, message
        threading.Thread(target=save, daemon=True).start()

    def status(self):
        return dict(active=self.active, scanning=self.scanning, straight_step=self.stepping, straight_steps=self.step_count, reached=self.reached,
                    retries=self.failures,
                    obstacle_paused=self.obstacle_hold,
                    elapsed=round(time.monotonic()-self.started, 1) if self.active else 0,
                    distance=round(self.nav.trail.length, 2), max_seconds=self.max_seconds,
                    max_distance=self.max_distance, max_speed=self.max_speed,
                    saved_map=self.saved_map, save_message=self.save_message)
