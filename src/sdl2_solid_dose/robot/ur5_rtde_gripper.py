"""
UR RTDE + RobotiqGripper Unified Wrapper
----------------------------------------
URArm: Unified interface for UR robot control using ur-rtde and RobotiqGripper
Location: Minimal pose utility (mm/deg <-> m/rad)
RobotiqGripper: TCP/IP control for Robotiq 2F/3F grippers

Author: Xiaoman Guo
"""

from rtde_control import RTDEControlInterface as rtc
from rtde_receive import RTDEReceiveInterface as rtr
import socket
import time
import math
import numpy as np
from scipy.spatial.transform import Rotation

# --- Main URArm wrapper ---
class URArm:
    """
    Unified interface for UR robot control using ur-rtde and RobotiqGripper.
    - All positions in mm/deg (legacy compatible)
    - All velocities in mm/s, gripper force/velocity in 0-1
    - Handles all conversions internally
    """
    def __init__(self, robot_ip, gripper_ip=None, gripper_id=1, gripper_port=63352, gripper_connect=True,
                 default_velocity: float = 250, max_velocity: float = 500, default_joint_velocity: float = 20.0, max_joint_velocity = 180.0,
                   gripper_default_velocity=0.5, gripper_default_force=0.5):
        self.robot_ip = robot_ip
        self._default_velocity = default_velocity  # mm/s
        self._default_joint_velocity = default_joint_velocity
        self._gripper_default_velocity = gripper_default_velocity
        self._gripper_default_force = gripper_default_force
        self._init_rtde()
        gip = gripper_ip if gripper_ip is not None else robot_ip
        self.gripper = RobotiqGripper(gip, id=gripper_id, base_port=gripper_port, connect=gripper_connect)

    def _init_rtde(self):
        try:
            self.rtde_c = rtc(self.robot_ip,
                              frequency=50,
                              )
            print("RTDEControl connected")
            self.rtde_r = rtr(self.robot_ip,
                              frequency=10,
                              )
            print("RTDEReceive connected")
        except Exception as e:
            print(f"[URArm] RTDE connect failed: {e}, will retry on next command.")
            self.rtde_c = None
            self.rtde_r = None

    def _reconnect_rtde(self):
        print("[URArm] Attempting RTDE reconnect...")
        self._init_rtde()

    def get_joints(self):
        # try:
        joints = self.rtde_r.getActualQ()
        # except Exception as e:
        #     print(f"[URArm] get_joints error: {e}, reconnecting...")
        #     self._reconnect_rtde()
        #     joints = self.rtde_r.getActualQ()
        return [math.degrees(j) for j in joints]

    def movej(self, joints, velocity: float = None, acceleration: float = None, async_move=False):
        vel = velocity if velocity is not None else self._default_velocity
        acc = acceleration if acceleration is not None else vel * 2
        joints_rad = [math.radians(j) for j in joints]
        vel_rad = math.radians(vel)
        acc_rad = math.radians(acc)
        try:
            self.rtde_c.moveJ(joints_rad, vel_rad, acc_rad, async_move)
        except Exception as e:
            print(f"[URArm] movej error: {e}, reconnecting...")
            self._reconnect_rtde()
            self.rtde_c.moveJ(joints_rad, vel_rad, acc_rad, async_move)

    def movel(self, pose, velocity: float = None, acceleration: float = None, async_move=False):
        if isinstance(pose, Location):
            pos_mm = pose.as_mm_deg()
        else:
            pos_mm = pose
        xyz_m = [p/1000 for p in pos_mm[:3]]
        rot = Rotation.from_euler('xyz', pos_mm[3:], degrees=True)
        rotvec = rot.as_rotvec()
        pos_m_rad = list(xyz_m) + list(rotvec)
        vel = velocity if velocity is not None else self._default_velocity
        acc = acceleration if acceleration is not None else vel * 2
        vel_m = vel / 1000
        acc_m = acc / 1000
        try:
            self.rtde_c.moveL(pos_m_rad, vel_m, acc_m, async_move)
        except Exception as e:
            print(f"[URArm] movel error: {e}, reconnecting...")
            self._reconnect_rtde()
            self.rtde_c.moveL(pos_m_rad, vel_m, acc_m, async_move)

    def get_tcp_pose(self, as_location: bool = False):
        # try:
        pos = self.rtde_r.getActualTCPPose()
        # except Exception as e:
        #     print(f"[URArm] get_tcp_pose error: {e}, reconnecting...")
        #     self._reconnect_rtde()
        #     pos = self.rtde_r.getActualTCPPose()
        xyz_mm = [p*1000 for p in pos[:3]]
        rotvec = np.array(pos[3:])
        rot = Rotation.from_rotvec(rotvec)
        euler_deg = rot.as_euler('xyz', degrees=True)
        pose_mm_deg = list(xyz_mm) + list(euler_deg)
        if as_location:
            return Location(pose_mm_deg[:3], pose_mm_deg[3:])
        return pose_mm_deg

    @property
    def location(self):
        return self.get_tcp_pose(as_location=True)

    @property
    def joint_positions(self) -> list:
        return self.get_joints()

    def open_gripper(self, position=None, force=None, velocity=None, wait=True, timeout=None):
        if force is None:
            force = self._gripper_default_force
        if velocity is None:
            velocity = self._gripper_default_velocity
        if timeout is None:
            timeout = 10.0
        self.gripper.move(position if position is not None else 0.0, force=force, velocity=velocity, wait=wait, timeout=timeout)
        print(f"Move gripper to position {position}.")

    def close_gripper(self, position=None, force=None, velocity=None, wait=True, timeout=None):
        if force is None:
            force = self._gripper_default_force
        if velocity is None:
            velocity = self._gripper_default_velocity
        if timeout is None:
            timeout = 10.0
        self.gripper.move(position if position is not None else 1.0, force=force, velocity=velocity, wait=wait, timeout=timeout)
        print(f"Move gripper to position {position}.")

    def set_gripper(self, value, force=None, velocity=None, wait=True, timeout=None):
        if force is None:
            force = self._gripper_default_force
        if velocity is None:
            velocity = self._gripper_default_velocity
        if timeout is None:
            timeout = 10.0
        return self.gripper.move(value, force=force, velocity=velocity, wait=wait, timeout=timeout)

    # def stop(self):
    #     self.rtde_c.stopJ(2.0)

    def disconnect(self):
        self.rtde_c.disconnect()
        self.rtde_r.disconnect()
        self.gripper.disconnect()
        print("Disconnected from robot and gripper.")

# --- Utility: Location class ---
class Location:
    """
    Minimal pose utility for UR robots.
    Stores position (mm) and orientation (deg, Euler xyz).
    Provides conversion to/from meters/radians and rotvec.
    """
    def __init__(self, position, orientation):
        self.position = list(position)
        self.orientation = list(orientation)

    @classmethod
    def from_list(cls, l):
        return cls(l[:3], l[3:])

    def as_mm_deg(self):
        return self.position + self.orientation

    def as_m_rad(self):
        return [p/1000 for p in self.position] + [math.radians(a) for a in self.orientation]

    def __repr__(self):
        return f"Location(position={self.position}, orientation={self.orientation})"

# --- RobotiqGripper error classes ---
class RobotiqGripperError(Exception): pass
class RobotiqGripperSetError(RobotiqGripperError): pass
class RobotiqGripperConnectionError(RobotiqGripperError): pass
class RobotiqGripperInvalidResponseError(RobotiqGripperError): pass
class RobotiqGripperInvalidForceError(RobotiqGripperError): pass
class RobotiqGripperInvalidSpeedError(RobotiqGripperError): pass
class RobotiqGripperInvalidPositionError(RobotiqGripperError): pass
class RobotiqGripperTimeoutError(RobotiqGripperError): pass

# --- RobotiqGripper class ---
class RobotiqGripper:
    STATUS_RESET = 0
    STATUS_ACTIVATING = 1
    STATUS_ACTIVE = 3

    def __init__(self, host: str, base_port: int = 63352, id: int = 1, timeout: float = 2.0, connect: bool = True):
        self.host = host
        self.port = base_port + id - 1
        self.timeout = timeout
        self.connection = None
        if connect:
            self.connect()

    @property
    def connected(self) -> bool:
        return self.connection is not None

    def connect(self):
        if self.connection:
            return
        self.connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connection.connect((self.host, self.port))
        self.connection.settimeout(self.timeout)

    def disconnect(self):
        if self.connection:
            self.connection.close()
            self.connection = None

    def request(self, request: bytes) -> bytes:
        self.connection.send(request + b'\n')
        response = self.connection.recv(1024)
        return response

    def set_registers(self, registers):
        command = 'SET ' + ' '.join([f'{name} {val}' for name, val in registers.items()])
        response = self.request(command.encode())
        if response != b'ack':
            raise RobotiqGripperSetError(f'Error setting registers, no ack received (response: {response})')

    def get_register(self, name: str) -> bytes:
        response = self.request(f'GET {name}'.encode())
        if not response.startswith(f'{name} '.encode()):
            raise RobotiqGripperInvalidResponseError(f'Invalid response: {response}')
        return response[len(name) + 1:].strip()

    @property
    def position_int(self) -> int:
        return int(self.get_register('POS'))

    @property
    def position(self) -> float:
        return self.position_int / 255.0

    def move(self, position: float, force: float = 0.5, velocity: float = 0.5, wait: bool = True, timeout: float = 10.0):
        if position < 0 or position > 1:
            raise RobotiqGripperInvalidPositionError(f'Invalid position, must be float between 0 and 1: {position}')
        if force < 0 or force > 1:
            raise RobotiqGripperInvalidForceError(f'Invalid force, must be float between 0 and 1: {force}')
        if velocity < 0 or velocity > 1:
            raise RobotiqGripperInvalidSpeedError(f'Invalid speed, must be float between 0 and 1: {velocity}')
        position_int = round(position * 255)
        force_int = round(force * 255)
        velocity_int = round(velocity * 255)
        self.set_registers({'POS': position_int, 'SPE': velocity_int, 'FOR': force_int, 'GTO': 1})
        if wait:
            self.wait_for_stop(timeout)

    def wait_for_stop(self, timeout: float = 10.0):
        last_pos = self.position_int
        start_time = time.time()
        while time.time() - start_time < timeout:
            time.sleep(0.1)
            current_pos = self.position_int
            if current_pos == last_pos:
                return
            last_pos = current_pos
        raise RobotiqGripperTimeoutError(f'Timeout while waiting for gripper to stop')
  
   