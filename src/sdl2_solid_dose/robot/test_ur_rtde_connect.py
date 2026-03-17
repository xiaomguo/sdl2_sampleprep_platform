from rtde_control import RTDEControlInterface as rtc
from rtde_receive import RTDEReceiveInterface as rtr
import time
import numpy as np
import os
from dotenv import load_dotenv

load_dotenv()

ROBOT_IP = os.environ.get("ROBOT_IP")

def test_movej():
    rtde_c = rtc(ROBOT_IP)
    rtde_r = rtr(ROBOT_IP)

    joints = rtde_r.getActualQ()
    print("Current joints:", joints)
    joints[-1] += 1
    print("Moving joints to:", joints)
    rtde_c.moveJ(joints, speed=0.5, acceleration=0.5, asynchronous=False)
    # joints: rads, speed: rads/s, acceleration: rads/s^2
    print("Moved joints to:", joints)
    joints[-1] -= 1
    print("Returning joints to:", joints)
    rtde_c.moveJ(joints, speed=0.5, acceleration=0.5,  asynchronous=False)
    print("Returned joints to:", joints)

if __name__ == "__main__":
    test_movej()