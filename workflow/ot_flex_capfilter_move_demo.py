from sdl2_solid_dose.opentrons import OTFlexProtocol

PIP_LEFT = "p1000"
TIP_START_WELL = "A1"
CAPFILTER_LABWARE = "capfilter_24"
CAPFILTER_TARGET_WELL = "A1"
TIP_Z_OFFSET_MM = 60
LIFT_AFTER_NEEDLE_MM = 65
SOURCE_LABWARE_C1 = "vial_plate_6"
SOURCE_WELL = "A1"
FILTER_BIN_LABWARE = "filter_bin"
FILTER_BIN_WELL = "A1"
ASPIRATE_VOLUME_UL = 0
SOURCE_TOP_MM = -45
ASPIRATE_FLOW_RATE_UL_S = 20
SAFE_TOP_MM_AT_FILTER_BIN = -5

# Post-aspirate gantry tuning settings (deck slot B1 reference frame).
SAFE_Z_AFTER_ASPIRATE_MM = 90
TUNE_B1_X_MM = 25
TUNE_B1_Y_MM = 35
TUNE_B1_Z_MM = 25
TUNE_X_JOG_MM = 5
TUNE_Z_JOG_MM = -5


def run_demo(simulation: bool = True) -> None:
    protocol = OTFlexProtocol(simulation=simulation)
    # try:
    # Pick up one tip from the left pipette tip rack.
    protocol.pick_up_tracked_tip(
        pip_name=PIP_LEFT,
        start_well=TIP_START_WELL,
        sample_id="capfilter_move_demo",
    )

    # Move pipette tip to the target location on custom capfilter labware.
    protocol.move_pipette_to_well(
        pip_name=PIP_LEFT,
        labware=CAPFILTER_LABWARE,
        well=CAPFILTER_TARGET_WELL,
        top=-13,
        speed=30,
    )

    # Needle lift: move up +65 mm in Z from current pipette location.
    protocol.move_pipette_relative_z(
        pip_name=PIP_LEFT,
        dz=LIFT_AFTER_NEEDLE_MM,
        speed=30,
    )

    # Move to C1 labware (vial_plate_6) A1 and aspirate liquid.
    protocol.ot.set_flow_rate(pip_name=PIP_LEFT, aspirate=ASPIRATE_FLOW_RATE_UL_S)
    protocol.aspirate_from(
        pip_name=PIP_LEFT,
        labware=SOURCE_LABWARE_C1,
        well=SOURCE_WELL,
        volume=ASPIRATE_VOLUME_UL,
        top=SOURCE_TOP_MM + TIP_Z_OFFSET_MM,
    )

    # Lift to a safe Z before any free gantry tuning move.
    protocol.move_pipette_relative_xyz(
        pip_name=PIP_LEFT,
        dz=70,
        speed=20,
        force_direct=True,
    )

    # Move to filter_bin on deck B1 at a safe Z offset (+50 mm from well top).
    protocol.move_pipette_to_well(
        pip_name=PIP_LEFT,
        labware=FILTER_BIN_LABWARE,
        well=FILTER_BIN_WELL,
        top=SAFE_TOP_MM_AT_FILTER_BIN,
        speed=30,
    )

    # Relative jog: move gantry -30 mm in X from the current location.
    protocol.move_pipette_relative_xyz(
        pip_name=PIP_LEFT,
        dx=-30,
        speed=20,
        force_direct=True,
    )

    protocol.move_pipette_relative_xyz(
        pip_name=PIP_LEFT,
        dz=50,
        speed=20,
        force_direct=True,
    )



    protocol.ot.delay(seconds=2)

         

    # finally:
        # protocol.drop_tip(pip_name=PIP_LEFT)
        # protocol.ot.home()
        # protocol.ot.home()


if __name__ == "__main__":
    run_demo(simulation=False)
