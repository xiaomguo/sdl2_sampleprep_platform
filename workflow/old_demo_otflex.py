import json
import os
from pathlib import Path

from dotenv import load_dotenv

from matterlab_opentrons import OpenTrons

load_dotenv()


class FlexDemoProtocol:
    """Clean OpenTrons Flex demo using local labware JSON settings."""

    def __init__(self, simulation: bool = True):
        self.simulation = simulation
        self.repo_root = Path(__file__).resolve().parents[1]
        self.labware_dir = self.repo_root / "settings" / "opentrons" / "labware"
        self._setup_connection()
        self._load_labware_and_instrument()

    def _setup_connection(self) -> None:
        otflex_password = os.environ.get("OPENTRONS_PASSWORD")
        if not otflex_password:
            raise ValueError(
                "OPENTRONS_PASSWORD is not set. Add it to your environment or .env file."
            )

        self.ot = OpenTrons(
            host_alias="otflex",
            password=otflex_password,
            simulation=self.simulation,
        )
        print("SSH connected.")
        self.ot.home()

    def _load_json(self, filename: str) -> dict:
        path = self.labware_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Labware JSON not found: {path}")
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _load_labware_and_instrument(self) -> None:
        vial_6_config = self._load_json("20mlvial_6_wellplate.json")
        al_24_config = self._load_json("al24wellplate_24_wellplate_15000ul.json")
        ph_unit_config = self._load_json("phunit.json")
        capfilter_24_config = self._load_json("capfilter_24.json")

        labware_defs = [
            {
                "nickname": "vial_plate_6",
                "loadname": "20mlvial_6_wellplate",
                "location": "C1",
                "ot_default": False,
                "config": vial_6_config,
            },
            {
                "nickname": "al_plate_24",
                "loadname": "al24wellplate",
                "location": "B3",
                "ot_default": False,
                "config": al_24_config,
            },
            {
                "nickname": "ph_unit",
                "loadname": "phunit",
                "location": "D1",
                "ot_default": False,
                "config": ph_unit_config,
            },
            {
                "nickname": "capfilter_24",
                "loadname": "capfilter_24",
                "location": "D2",
                "ot_default": False,
                "config": capfilter_24_config,
            },
            {
                "nickname": "plate_96_1",
                "loadname": "corning_96_wellplate_360ul_flat",
                "location": "C2",
                "ot_default": True,
                "config": {},
            },
            {
                "nickname": "tip_1000_96_1",
                "loadname": "opentrons_flex_96_filtertiprack_1000ul",
                "location": "A2",
                "ot_default": True,
                "config": {},
            },
        ]

        for lw in labware_defs:
            self.ot.load_labware(lw)

        self.ot.load_trash_bin()
        self.ot.load_instrument(
            {
                "nickname": "p1000",
                "instrument_name": "flex_1channel_1000",
                "mount": "left",
                "tip_racks": ["tip_1000_96_1"],
                "ot_default": True,
            }
        )

    def run_demo(self) -> None:
        """Simple demo: transfer from 24-well plate to 96-well plate and mix."""
        transfer_plan = [
            ("A1", "A1", 200),
            ("A2", "A2", 200),
            ("A3", "A3", 200),
        ]
        tip_wells = ["A1", "A2", "A3"]

        for (source_well, target_well, volume), tip_well in zip(transfer_plan, tip_wells):
            self.ot.get_location_from_labware(
                labware_nickname="tip_1000_96_1", position=tip_well, top=0
            )
            self.ot.pick_up_tip(pip_name="p1000")

            self.ot.get_location_from_labware(
                "al_plate_24", position=source_well, top=-20
            )
            self.ot.aspirate(pip_name="p1000", volume=volume)

            self.ot.get_location_from_labware(
                "plate_96_1", position=target_well, top=1, y_offset=1
            )
            self.ot.dispense(pip_name="p1000", volume=volume)

            for _ in range(2):
                self.ot.get_location_from_labware(
                    "plate_96_1", position=target_well, top=-4, y_offset=1
                )
                self.ot.aspirate(pip_name="p1000", volume=100)
                self.ot.dispense(pip_name="p1000", volume=100)

            self.ot.drop_tip(pip_name="p1000")

        self.ot.home()
        print("Flex demo finished.")


if __name__ == "__main__":
    demo = FlexDemoProtocol(simulation=True)
    demo.run_demo()

