import time
from matterlab_hotplates import IKAHotplate

hp = IKAHotplate("COM7")

hp.rpm = 400

time.sleep(15)

hp.rpm = 0