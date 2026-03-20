import time

from matterlab_balances import MTXPRBalanceDoors
from sdl2_solid_dose import URController
from sdl2_solid_dose.balance.balance_protocol import BalanceProtocol
from sdl2_solid_dose.opentrons import OTFlexProtocol
from sdl2_solid_dose.ph_module.image_req_client import pHAnalyzer

POWDER_NAME = "Gum"
DOSE_HEAD_LOCATION = "A2"  # Gum in settings/robot/dosing_heads.json
TARGET_WEIGHT_MG = 30
MAX_ATTEMPTS = 3

PIP_50 = "p50"
PIP_1000 = "p1000"
SAFE_IKA = "safe_ika"
IKA_UNIT = "ika_unit"
IKA_WELL = "A1"
PH_UNIT = "ph_unit"
PH_WELL = "A1"
ASPIRATE_FLOW_RATE_UL_S = 20
TRANSFER_VOLUME_UL = 50
OT_LAYOUT = "settings/opentrons/gelation_bath_workflow_0318_layout.json"
TIPRACK_50 = "tip_50_96_1"
TIPRACK_1000 = "tip_1000_96_1"
TIP_STATE_1000 = "settings/opentrons/state/tip_tracking_1000_demo.json"
TIP_STATE_50 = "settings/opentrons/state/tip_tracking_50_demo.json"
NAOH_VOLUME_UL = 100
HCL_VOLUME_UL = 100


def initialize_opentrons(protocol: OTFlexProtocol) -> None:
	"""Initialize OT hardware/modules for this workflow."""
	# Layout/instruments are loaded during OTFlexProtocol construction.
	protocol.ot.home()

def run_robot_and_solid_dosing_step() -> None:
	"""Run solid dosing and move the flat vial to the OT deck."""
	balance_protocol = BalanceProtocol()
	rob = URController()

	rob.home()
	rob.activate_gripper()
	rob.gripper_pos(rob.gripper_dist["open"]["flat_vial"])

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


def ph_measure_step(protocol: OTFlexProtocol) -> None:
	"""Use p1000 to transfer liquid from ika_unit A1 to ph_unit A1."""
	PH= pHAnalyzer()
	protocol.pick_up_tracked_tip(
		pip_name=PIP_1000,
		tiprack_nickname=TIPRACK_1000,
		sample_id=f"{IKA_UNIT}_{IKA_WELL}",
		start_well="A1",
	)
	protocol.move_pipette_to_well(
		pip_name=PIP_1000,
		labware=SAFE_IKA,
		well="A1",
	)
	protocol.move_pipette_to_well(
		pip_name=PIP_1000,
		labware=IKA_UNIT,
		well=IKA_WELL,
	)
	protocol.ot.set_flow_rate(pip_name=PIP_1000, aspirate=ASPIRATE_FLOW_RATE_UL_S)
	protocol.aspirate_from(
		pip_name=PIP_1000,
		labware=IKA_UNIT,
		well=IKA_WELL,
		volume=TRANSFER_VOLUME_UL,
		top=-60,
	)
	protocol.move_pipette_to_well(
		pip_name=PIP_1000,
		labware=SAFE_IKA,
		well="A1",
	)
	# protocol.move_pipette_to_well(
	# 	pip_name=PIP_1000,
	# 	labware="vial_plate_6",
	# 	well="A1",
	# 	top=115.5,
	# )

	# Measure pH
	protocol.dispense_to(
		pip_name=PIP_1000,
		labware=PH_UNIT,
		well=PH_WELL,
		volume=TRANSFER_VOLUME_UL,
	)
	time.sleep(1)  # Wait for liquid to settle before reading
	for attempt in range(3):
		PH.disconnect()
		if PH.connect():
			result = PH.read_ph()
			if result is not None:
				break
		print(f"pH read attempt {attempt + 1}/3 failed, retrying...")
		if attempt == 2:
			raise RuntimeError("pH read failed after 3 attempts. Check server connection.")
		time.sleep(3)
	PH.dispense_strip()

	protocol.drop_tip(pip_name=PIP_1000)
	# protocol.ot.home()

REAGENT_WELLS = {
	"NaOH": "B1",
	"HCl": "A1",
}
REAGENT_VOLUME_UL = 100
VIAL_PLATE = "vial_plate_6"

# add NaOH and HCL
def liquid_addition_step(protocol: OTFlexProtocol, reagent: str = "HCl") -> None:
	"""Aspirate NaOH or HCl from vial_plate_6 and dispense into ika_unit.

	Args:
		reagent: "NaOH" (well B1) or "HCl" (well A1).
	"""
	if reagent not in REAGENT_WELLS:
		raise ValueError(f"reagent must be one of {list(REAGENT_WELLS)}, got '{reagent}'")

	reagent_well = REAGENT_WELLS[reagent]

	protocol.pick_up_tracked_tip(
		pip_name=PIP_1000,
		tiprack_nickname=TIPRACK_1000,
		sample_id=f"liquid_addition_{reagent}",
		start_well="A1",
	)
	protocol.move_pipette_to_well(
		pip_name=PIP_1000,
		labware=VIAL_PLATE,
		well=reagent_well,
	)
	protocol.aspirate_from(
		pip_name=PIP_1000,
		labware=VIAL_PLATE,
		well=reagent_well,
		volume=REAGENT_VOLUME_UL,
		top=-40,
	)
	protocol.move_pipette_to_well(
		pip_name=PIP_1000,
		labware=SAFE_IKA,
		well="A1",
	)
	protocol.move_pipette_to_well(
		pip_name=PIP_1000,
		labware=IKA_UNIT,
		well=IKA_WELL,
	)
	protocol.dispense_to(
		pip_name=PIP_1000,
		labware=IKA_UNIT,
		well=IKA_WELL,
		volume=REAGENT_VOLUME_UL,
		top = -40,
	)
	protocol.move_pipette_to_well(
		pip_name=PIP_1000,
		labware=SAFE_IKA,
		well="A1",
	)
	protocol.drop_tip(pip_name=PIP_1000)
	protocol.ot.home()

def close_opentrons(protocol: OTFlexProtocol) -> None:
	"""Close an initialized OT Flex protocol session."""
	protocol.close()


if __name__ == "__main__":
	protocol = OTFlexProtocol(
		simulation=False,
		layout_relpath=OT_LAYOUT,
		tip_state_relpaths={
			TIPRACK_1000: TIP_STATE_1000,
			TIPRACK_50: TIP_STATE_50,
		},
	)

	# Opentrons callable functions
	#initialize_opentrons(protocol)
	# liquid_addition_step(protocol, reagent="NaOH")
	# liquid_addition_step(protocol, reagent="HCl")
	ph_measure_step(protocol)

	# Other callable functions (commented for now)
	# close_opentrons(protocol)
	# run_robot_and_solid_dosing_step()




