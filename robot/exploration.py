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

    def start(self):
        n = self.nav
        n.check_ready()
        if not n.planner.server_is_ready():
            raise ValueError('Path planning service is not ready')
        self.active = True
        self.scanning = self.scan_attempted = False
        self.stepping = False
        self.step_count = 0
        self.wait_revision = None
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
            n.stop('No footprint-safe reachable frontier. Stopped; continue manual mapping to reveal a route.', 'failed')
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
                        n.stop('No footprint-safe reachable frontier. Stopped; continue manual mapping to reveal a route.', 'failed')
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
                    max_distance=self.max_distance, max_speed=.5,
                    saved_map=self.saved_map, save_message=self.save_message)
