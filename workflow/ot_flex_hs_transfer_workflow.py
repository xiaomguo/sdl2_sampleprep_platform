from sdl2_solid_dose.opentrons import OTFlexProtocol

PIP_1000 = "p1000"
SRC_plate_6 = "vial_plate_6"
SRC_WELL = "A1"
DST_plate_24 = "al_plate_24"
DST_WELLS = ["A6", "B6", "C6", "D6"]
TRANSFER_VOLUME_SOLVENT_UL = 500

SRC_plate_24 = "al_plate_24"
SRC_WELLS_24 = ["A6", "B6", "C6", "D6"]
DST_plate_54 = "hplc_plate_54"
DST_WELLS_54 = ["A9", "B9", "C9", "D9"]
TRANSFER_VOLUME_UL_SAMPLE = 100

PIP_1000 = "p1000"
SRC_plate_6 = "vial_plate_6"
SRC_WELL_2 = "B1"
DST_plate_54 = "hplc_plate_54"
DST_WELLS_54 = ["A9", "B9", "C9", "D9"]
TRANSFER_VOLUME_UL_DILUTION = 900


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


def run_workflow(simulation: bool = True) -> None:
    protocol = OTFlexProtocol(simulation=simulation)
    try:
        # Load heater-shaker module without adapter for custom labware.
        protocol.load_module(
            nickname=HS_NICKNAME,
            module_name=HS_MODULE_NAME,
            location=HS_LOCATION,
            adapter=HS_ADAPTER,
        )

        # # 1) Transfer 0.5 mL from 20 mL vial A1 to al_plate wells.
        # for well in DST_WELLS:
        #     protocol.transfer(
        #         pip_name=PIP_1000,
        #         source_labware=SRC_plate_6,
        #         source_well=SRC_WELL,
        #         dest_labware=DST_plate_24,
        #         dest_well=well,
        #         volume=TRANSFER_VOLUME_SOLVENT_UL,
        #         compound=f"{SRC_plate_6}_{SRC_WELL}",
        #         source_top=-48,
        #         dest_top=0,
        #         start_well="A1",
        #     )

        # # 2) Move al_plate to heater-shaker (open/close latch around move).
        # protocol.hs_latch_open(nickname=HS_NICKNAME)
        # hs_target_used = move_plate_to_hs(protocol, labware_nickname=DST_plate_24)
        # print(f"Moved {DST_plate_24} to heater-shaker target: {hs_target_used}")
        # protocol.hs_latch_close(nickname=HS_NICKNAME)

        # # 3) Shake for a few seconds.
        # protocol.hs_set_and_wait_shake_speed(nickname=HS_NICKNAME, rpm=SHAKE_RPM)
        # protocol.ot.delay(seconds=SHAKE_SECONDS)
        # protocol.hs_deactivate_shaker(nickname=HS_NICKNAME)

        # # 4) Move plate back to original slot.
        # protocol.hs_latch_open(nickname=HS_NICKNAME)
        # protocol.move_labware_with_gripper(
        #     labware_nickname=DST_plate_24,
        #     new_location=PLATE_HOME_SLOT,
        # )
        # protocol.hs_latch_close(nickname=HS_NICKNAME)
        # # 4) Sampling 0.1mL from al_plate_24 to HPLC vial
        # for src_well, dst_well in zip(SRC_WELLS_24, DST_WELLS_54):
        #     protocol.transfer(
        #         pip_name=PIP_1000,
        #         source_labware=SRC_plate_24,
        #         source_well=src_well,
        #         dest_labware=DST_plate_54,
        #         dest_well=dst_well,
        #         volume=TRANSFER_VOLUME_UL_SAMPLE,
        #         compound=f"{SRC_plate_24}_{src_well}",
        #         source_top=-35,
        #         dest_top=0,
        #         start_well="A1",
        #     )
        # # 5) Dilution from vial to HPLC vial
        for src_well, dst_well in zip([SRC_WELL_2], DST_WELLS_54):
            protocol.transfer(
                pip_name=PIP_1000,
                source_labware=SRC_plate_6,
                source_well=SRC_WELL_2,
                dest_labware=DST_plate_54,
                dest_well=DST_WELLS_54,
                volume=TRANSFER_VOLUME_UL_DILUTION,
                compound=f"{SRC_plate_6}_{SRC_WELL_2}",
                source_top=-48,
                dest_top=0,
                start_well="A1",
            )



        protocol.ot.home()
    finally:
        protocol.close()


if __name__ == "__main__":
    run_workflow(simulation=True)
