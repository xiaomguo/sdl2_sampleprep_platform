import time

from matterlab_balances import MTXPRBalanceDoors
from sdl2_solid_dose import BalanceProtocol, URController
from sdl2_solid_dose.opentrons import OTFlexProtocol

PIP_1000 = "p1000"
SRC_PLATE_1 = "vial_plate_6"
SRC_WELL_1 = "A1"
DST_PLATE_1 = "printed_24wellplate"
DST_WELLS_1 = ["A6"]
TRANSFER_VOLUME_SOLVENT_UL = 1000
DEST_MIX_DEPTH_MM = 20
DEST_MIX_CYCLES = 0
DEST_MIX_VOLUME_UL = 500

SRC_PLATE_2 = "printed_24wellplate"
SRC_WELLS_2 = ["A6"]
DST_PLATE_2 = "hplc_plate_54"
DST_WELLS_2 = ["A9"]
TRANSFER_VOLUME_UL_SAMPLE = 100
SOURCE_PREMIX_CYCLES = 0
SOURCE_PREMIX_VOLUME_UL = 500

PIP_1000 = "p1000"
SRC_PLATE_3 = "vial_plate_6"
SRC_WELL_3 = "B1"
DST_PLATE_3 = "hplc_plate_54"
DST_WELLS_3 = ["A9"]
TRANSFER_VOLUME_UL_DILUTION = 900
DILUTION_DEST_MIX_CYCLES = 2
DILUTION_DEST_MIX_VOLUME_UL = 200

DOSE_PLAN = [
    ("A1", 20),
]


HS_NICKNAME = "hs"
HS_MODULE_NAME = "heaterShakerModuleV1"
HS_LOCATION = "A1"
HS_ADAPTER = None
PLATE_HOME_SLOT = "B3"
SHAKE_RPM = 500
SHAKE_SECONDS = 5


def move_plate_to_hs(protocol: OTFlexProtocol, *, labware_nickname: str) -> str:
    protocol.move_labware_with_gripper_to_module(
        labware_nickname=labware_nickname,
        module_nickname=HS_NICKNAME,
    )
    return HS_NICKNAME


def run_dose_plan(*, dose_plan: list[tuple[str, float]]) -> None:
    """Run solid dosing and return vial to OT deck."""
    balance = BalanceProtocol()
    rob = URController()

    rob.home()
    rob.activate_gripper()

    # Move vial to balance once, then perform all dosing steps.
    balance.open_door(MTXPRBalanceDoors.RIGHT_OUTER)
    time.sleep(1)
    rob.vial_2_balance("A1")

    for head_location, target_weight_mg in dose_plan:
        head = balance.get_head_info(head_location)
        print(f"Using head {head_location}: {head['head_name']} -> {target_weight_mg} mg")
        rob.dose_2_balance(head_location)

        balance.close_door(MTXPRBalanceDoors.RIGHT_OUTER)
        balance.auto_dose_from_head(
            head_location=head_location,
            target_weight_mg=target_weight_mg,
            validate_loaded_head=False,
        )
        rob.dose_balance_2_stock(head_location)
        time.sleep(1)

    # Move vial back after all powders are dosed.
    balance.open_door(MTXPRBalanceDoors.RIGHT_OUTER)
    time.sleep(1)
    balance.open_door(MTXPRBalanceDoors.RIGHT_OUTER)
    rob.vial_2_OT("A1")


def initialize_opentrons(protocol: OTFlexProtocol) -> None:
    """Initialize OT hardware/module before solid dosing starts."""
    protocol.load_module(
        nickname=HS_NICKNAME,
        module_name=HS_MODULE_NAME,
        location=HS_LOCATION,
        adapter=HS_ADAPTER,
    )


def run_workflow_steps(protocol: OTFlexProtocol) -> None:
    # 1) Transfer 1 mL from 20 mL vial A1 to printed_24wellplate wells.
    for well in DST_WELLS_1:
        protocol.pick_up_tracked_tip(
            pip_name=PIP_1000,
            sample_id=f"{SRC_PLATE_1}_{SRC_WELL_1}",
            start_well="A1",
        )
        protocol.transfer_liquid(
            pip_name=PIP_1000,
            source_labware=SRC_PLATE_1,
            source_well=SRC_WELL_1,
            dest_labware=DST_PLATE_1,
            dest_well=well,
            volume=TRANSFER_VOLUME_SOLVENT_UL,
            source_top=-48,
            dest_top=-10,
        )
        for _ in range(DEST_MIX_CYCLES):
            protocol.aspirate_from(
                pip_name=PIP_1000,
                labware=DST_PLATE_1,
                well=well,
                volume=DEST_MIX_VOLUME_UL,
                top=-40,
            )
            protocol.dispense_to(
                pip_name=PIP_1000,
                labware=DST_PLATE_1,
                well=well,
                volume=DEST_MIX_VOLUME_UL,
                top=-40,
            )
        protocol.drop_tip(pip_name=PIP_1000)

    # 2) Move al_plate to heater-shaker (open/close latch around move).
    protocol.hs_latch_open(nickname=HS_NICKNAME)
    hs_target_used = move_plate_to_hs(protocol, labware_nickname=DST_PLATE_1)
    print(f"Moved {DST_PLATE_1} to heater-shaker target: {hs_target_used}")
    protocol.hs_latch_close(nickname=HS_NICKNAME)

    # 3) Shake for a few seconds.
    protocol.hs_set_and_wait_shake_speed(nickname=HS_NICKNAME, rpm=SHAKE_RPM)
    protocol.ot.delay(seconds=SHAKE_SECONDS)
    protocol.hs_deactivate_shaker(nickname=HS_NICKNAME)

    # 4) Move plate back to original slot.
    protocol.hs_latch_open(nickname=HS_NICKNAME)
    protocol.move_labware_with_gripper(
        labware_nickname=DST_PLATE_1,
        new_location=PLATE_HOME_SLOT,
    )
    protocol.hs_latch_close(nickname=HS_NICKNAME)
    # 4) Sampling 0.1mL from al_plate_24 to HPLC vial
    for src_well, dst_well in zip(SRC_WELLS_2, DST_WELLS_2):
        protocol.pick_up_tracked_tip(
            pip_name=PIP_1000,
            sample_id=f"{SRC_PLATE_2}_{src_well}",
            start_well="A1",
        )
        for _ in range(SOURCE_PREMIX_CYCLES):
            protocol.aspirate_from(
                pip_name=PIP_1000,
                labware=SRC_PLATE_2,
                well=src_well,
                volume=SOURCE_PREMIX_VOLUME_UL,
                top=-40,
            )
            protocol.dispense_to(
                pip_name=PIP_1000,
                labware=SRC_PLATE_2,
                well=src_well,
                volume=SOURCE_PREMIX_VOLUME_UL,
                top=-40,
            )

        protocol.transfer_liquid(
            pip_name=PIP_1000,
            source_labware=SRC_PLATE_2,
            source_well=src_well,
            dest_labware=DST_PLATE_2,
            dest_well=dst_well,
            volume=TRANSFER_VOLUME_UL_SAMPLE,
            source_top=-40,
            dest_top=-10,
        )
        protocol.drop_tip(pip_name=PIP_1000)
    # 5) Dilution from vial to HPLC vial
    for dst_well in DST_WELLS_3:
        protocol.pick_up_tracked_tip(
            pip_name=PIP_1000,
            sample_id=f"{SRC_PLATE_3}_{SRC_WELL_3}",
            start_well="A1",
        )
        protocol.transfer_liquid(
            pip_name=PIP_1000,
            source_labware=SRC_PLATE_3,
            source_well=SRC_WELL_3,
            dest_labware=DST_PLATE_3,
            dest_well=dst_well,
            volume=TRANSFER_VOLUME_UL_DILUTION,
            source_top=-48,
            dest_top=-10,
        )
        for _ in range(DILUTION_DEST_MIX_CYCLES):
            protocol.aspirate_from(
                pip_name=PIP_1000,
                labware=DST_PLATE_3,
                well=dst_well,
                volume=DILUTION_DEST_MIX_VOLUME_UL,
                top=-20,
            )
            protocol.dispense_to(
                pip_name=PIP_1000,
                labware=DST_PLATE_3,
                well=dst_well,
                volume=DILUTION_DEST_MIX_VOLUME_UL,
                top=-20,
            )
        protocol.drop_tip(pip_name=PIP_1000)
    protocol.ot.home()


def run_workflow(simulation: bool = True) -> None:
    protocol = OTFlexProtocol(simulation=simulation)
    try:
        initialize_opentrons(protocol)
        run_workflow_steps(protocol)
    finally:
        protocol.close()


def run_full_workflow(simulation: bool = False) -> None:
    """Start OT first, run solid dosing, then execute OT Flex steps."""
    protocol = OTFlexProtocol(simulation=simulation)
    try:
        initialize_opentrons(protocol)
        run_dose_plan(dose_plan=DOSE_PLAN)
        run_workflow_steps(protocol)
    finally:
        protocol.close()


if __name__ == "__main__":
    run_full_workflow(simulation=False)
