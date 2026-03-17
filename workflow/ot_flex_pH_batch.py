from typing import NamedTuple, List
import os
import csv
import sys
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from matterlab_opentrons import OpenTrons
from pH_measure.pizerocam.src.image_req_client.ph_analyzer_new_0_6range import pHAnalyzer
import time
import json
from pathlib import Path
from datetime import datetime



# Define the experiment type
class PhExperiment(NamedTuple):
    well: str
    stock1_volume: float
    stock2_volume: float
    stock3_volume: float

# Setup OpenTrons
class PhProtocol:
    def __init__(self, simulation: bool = True):
        load_dotenv()
        self.otflex_setup(simulation)
        self.load_labware_and_instruments()

    def otflex_setup(self, simulation: bool = True):
        otflex_password = os.environ.get("OPENTRONS_PASSWORD")
        if not otflex_password:
            raise ValueError("OPENTRONS_PASSWORD is not set in the environment. Please add it to your .env file without quotes or spaces.")
        self.ot = OpenTrons(host_alias="otflex", password=otflex_password, simulation=simulation)
        print(self.ot.invoke("print([slot for slot in protocol.deck])"))
        print("SSH connected.")
        print(self.ot.invoke("from opentrons import execute"))
        print(self.ot.invoke("protocol = execute.get_protocol_api('2.21')"))
        self.ot.home()    


    def load_labware_and_instruments(self):
        # Load custom labware
        vial_config_6 = json.load(open(Path(r"C:\Users\xmguo\project\solid_dosing\matterlab_opentrons\20mlvial_6_wellplate.json")))
        ph_config = json.load(open(Path(r"C:\Users\xmguo\project\solid_dosing\matterlab_opentrons\phunit.json")))
        vial_config_24 = json.load(open(Path(r"C:\Users\xmguo\project\solid_dosing\matterlab_opentrons\al24wellplate_24_wellplate_15000ul.json")))

        plates = [
            {"nickname": "plate_96_1", "loadname": "corning_96_wellplate_360ul_flat", "location": "C2", "ot_default": True, "config": {}},
            {"nickname": "vial_plate_6", "loadname": "20mlvial_6_wellplate", "location": "C1", "ot_default": False, "config": vial_config_6},
            {"nickname": "phunit", "loadname": "phunit", "location": "D1", "ot_default": False, "config": ph_config},
            {"nickname": "vial_plate_24", "loadname": "al24wellplate", "location": "B3", "ot_default": False, "config": vial_config_24}
        ]

        tips = [
            {"nickname": "tip_1000_96_1", "loadname": "opentrons_flex_96_filtertiprack_1000ul", "location": "A2", "ot_default": True, "config": {}},
            {"nickname": "tip_50_96_1", "loadname": "opentrons_flex_96_filtertiprack_50ul", "location": "B2", "ot_default": True, "config": {}}
        ]

        for plate in plates:
            self.ot.load_labware(plate)
        for tip in tips:
            self.ot.load_labware(tip)

        self.ot.load_trash_bin()
        self.ot.load_instrument({"nickname": "p1000", "instrument_name": "flex_1channel_1000", "mount": "left", "tip_racks": ["tip_1000_96_1"], "ot_default": True})


    # Run a batch
    def run_batch(self, batch: List[PhExperiment]):
        ot = self.ot
        results: List[float] = []

        wells = [exp.well for exp in batch]

        # -------------------------
        # 0.01M HCl Stock1 in A1
        # Acid with ONE tip
        # -------------------------
        ot.pick_up_tip(pip_name="p1000")

        for exp in batch:
            if exp.stock1_volume == 0:
                continue
            # Aspirate acid
            ot.get_location_from_labware("vial_plate_6", position="A1", top=-48)
            # ot.move_to_pip(pip_name="p1000")
            ot.aspirate(pip_name="p1000", volume=exp.stock1_volume)

            # Dispense into target well
            ot.get_location_from_labware("plate_96_1", position=exp.well, top=0, y_offset=1)
            # ot.move_to_pip(pip_name="p1000")
            ot.dispense(pip_name="p1000", volume=exp.stock1_volume)

        ot.drop_tip(pip_name="p1000")


        # -------------------------
        # 0.1M HOAc Stock2 in B1
        # with ONE tip
        # -------------------------
        ot.pick_up_tip(pip_name="p1000")

        for exp in batch:
            if exp.stock2_volume == 0:
                continue
            # Aspirate base
            ot.get_location_from_labware("vial_plate_6", position="B1", top=-48)
            ot.move_to_pip(pip_name="p1000")
            ot.aspirate(pip_name="p1000", volume=exp.stock2_volume)

            # Dispense into target well
            ot.get_location_from_labware("plate_96_1", position=exp.well, top=0, y_offset=1)
            ot.move_to_pip(pip_name="p1000")
            ot.dispense(pip_name="p1000", volume=exp.stock2_volume)

        ot.drop_tip(pip_name="p1000")


        # -------------------------
        # 0.1M NaOAc Stock3 in A2
        # with ONE tip
        # -------------------------
        ot.pick_up_tip(pip_name="p1000")

        for exp in batch:
            if exp.stock3_volume == 0:
                continue
            # Aspirate water
            ot.get_location_from_labware("vial_plate_6", position="A2", top=-48)
            ot.move_to_pip(pip_name="p1000")
            ot.aspirate(pip_name="p1000", volume=exp.stock3_volume)

            # Dispense into target well
            ot.get_location_from_labware("plate_96_1", position=exp.well, top=0, y_offset=1)
            ot.move_to_pip(pip_name="p1000")
            ot.dispense(pip_name="p1000", volume=exp.stock3_volume)

        ot.drop_tip(pip_name="p1000")


        # -------------------------
        # Mix + pH test (NEW TIP per well)
        # -------------------------

        for exp in batch:
            print(f"--- Mixing and measuring pH for {exp.well} ---")

            ot.pick_up_tip(pip_name="p1000")

            # Mix 3× 
            for _ in range(3):
                ot.get_location_from_labware("plate_96_1", position=exp.well, top=-7, y_offset=1)
                #ot.move_to_pip(pip_name="p1000")
                ot.aspirate(pip_name="p1000", volume=300)
                ot.dispense(pip_name="p1000", volume=300)

            all_ph = []
            for _ in range(1):  # Repeat aspirate/dispense 3 times
                # Aspirate for pH test
                ot.get_location_from_labware("plate_96_1", position=exp.well, top=-7, y_offset=1)
                ot.move_to_pip(pip_name="p1000")
                ot.aspirate(pip_name="p1000", volume=12)

                # Move to pH unit
                ph_location = ot.get_location_from_labware("phunit", position="A1", top=-7)
                ot.move_to_pip(pip_name="p1000")

                # Prepare strip
                analyzer = pHAnalyzer()
                analyzer.dispense_strip()

                # Dispense into pH strip
                ot.dispense(pip_name="p1000", volume=12)

                time.sleep(2)
                ph_list = []
                for _ in range(3):  # For each dispensing, measure 3 times
                    ph_value = analyzer.read_ph(well=exp.well)
                    ph_list.append(ph_value)
                all_ph.extend(ph_list)

                analyzer.dispense_strip()
                # time.sleep(1)
                # analyzer.dispense_strip()

            # Cleanup
            ot.drop_tip(pip_name="p1000")
            results.append(all_ph)
        ot.home()
        return results


# Example usage
if __name__ == "__main__":
    # # Example experiments
    # batch = [
    #     PhExperiment(well="A1", stock1_volume=350, stock2_volume=0, stock3_volume=0),
    #     PhExperiment(well="A2", stock1_volume=0, stock2_volume=350, stock3_volume=0),
    #     PhExperiment(well="A3", stock1_volume=0, stock2_volume=300, stock3_volume=50),
    #     PhExperiment(well="A4", stock1_volume=0, stock2_volume=250, stock3_volume=100),
    #     PhExperiment(well="A5", stock1_volume=0, stock2_volume=200, stock3_volume=150),
    #     PhExperiment(well="A6", stock1_volume=0, stock2_volume=175, stock3_volume=175),
    #     PhExperiment(well="A7", stock1_volume=0, stock2_volume=150, stock3_volume=200),
    #     PhExperiment(well="A8", stock1_volume=300, stock2_volume=0, stock3_volume=50),
    #     PhExperiment(well="A9", stock1_volume=250, stock2_volume=0, stock3_volume=100),
    #     PhExperiment(well="A10", stock1_volume=200, stock2_volume=0, stock3_volume=150),
    #     PhExperiment(well="A11", stock1_volume=40, stock2_volume=155, stock3_volume=155),
    #     PhExperiment(well="A12", stock1_volume=80, stock2_volume=135, stock3_volume=135),

    # ]
    # Load batch from CSV file
    batch = []
    csv_path = r"C:\SDL2 project\Automated pH detect\Feb13 experiment\Feb_13_experiment1.csv"
    with open(csv_path, newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            batch.append(
                PhExperiment(
                    well=row["well"],
                    stock1_volume=float(row["stock1_volume"]),
                    stock2_volume=float(row["stock2_volume"]),
                    stock3_volume=float(row["stock3_volume"])
                )
            )
    protocol = PhProtocol(simulation=True)
    results = protocol.run_batch(batch)
    print("Batch results:", results)

    # Save results to CSV
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    date_folder = datetime.now().strftime("%Y%m%d")
    output_dir = Path(r"C:\SDL2 project\Automated pH detect") / date_folder
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / f"ph_results_{ts}.csv"
    with open(csv_path, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["well", "v_0.01M_HCl_acid", "v_0.1M_HOAc", "v_0.1M_NaOAc", "pH"])
        #writer.writerow(["well", "v_0.1M_CitricAcid", "v_0.1M_HOAc", "v_0.1M_NaOAc", "pH"])
        for exp, ph_list in zip(batch, results):
            for ph in ph_list:  # ph_list is a list of 3 pH values
                # If ph is a dict like {'ph': value}, extract and format
                if isinstance(ph, dict) and 'ph' in ph:
                    ph_val = float(ph['ph'])
                else:
                    ph_val = float(ph)
                writer.writerow([
                    exp.well,
                    exp.stock1_volume,
                    exp.stock2_volume,
                    exp.stock3_volume,
                    f"{ph_val:.2f}"
                ])
