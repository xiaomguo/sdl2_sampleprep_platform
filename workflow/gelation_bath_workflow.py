import os,time
from matterlab_balances import MTXPRBalance, MTXPRBalanceDoors
from sdl2_solid_dose import URController
from sdl2_solid_dose.balance.balance_protocol import BalanceProtocol

POWDER_NAME = "Gum"
DOSE_HEAD_LOCATION = "A2"  # Gum in settings/robot/dosing_heads.json
TARGET_WEIGHT_MG = 30
MAX_ATTEMPTS = 3
FLAT_VIAL_LOC = "A1"

balance_protocol = BalanceProtocol()
rob = URController()

rob.home()
rob.activate_gripper()
rob.gripper_pos(rob.gripper_dist["open"]["flat_vial"])
# rob.dose_2_balance(DOSE_HEAD_LOCATION)
# rob.vial_2_balance(FLAT_VIAL_LOC)

print(
	f"Starting auto-dose: powder={POWDER_NAME}, head={DOSE_HEAD_LOCATION}, "
	f"target={TARGET_WEIGHT_MG}mg, attempts={MAX_ATTEMPTS}"
)
ok = balance_protocol.auto_dose_from_head_with_retry(
	head_location=DOSE_HEAD_LOCATION,
	target_weight_mg=TARGET_WEIGHT_MG,
	max_attempts=MAX_ATTEMPTS,
	validate_loaded_head=False,
)

if not ok:
	raise RuntimeError("Auto-dose failed after max attempts.")

balance_protocol.open_door(MTXPRBalanceDoors.RIGHT_OUTER)
time.sleep(1)

rob.flatvial_2_OT()