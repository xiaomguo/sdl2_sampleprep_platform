from dataclasses import dataclass
from datetime import datetime
import csv
from pathlib import Path
from typing import Sequence

from sdl2_solid_dose.opentrons import OTFlexProtocol

PIP_1000 = "p1000"
TIP_START_WELL = "A1"

LW_VIAL_STOCK = "vial_plate_6"
LW_TARGET_PLATE = "plate_96_1"
LW_PH_UNIT = "ph_unit"
PH_UNIT_WELL = "A1"


@dataclass(frozen=True)
class PhExperiment:
    well: str
    stock1_volume: float
    stock2_volume: float
    stock3_volume: float


def build_batch() -> list[PhExperiment]:
    return [
        PhExperiment(well="A1", stock1_volume=350, stock2_volume=0, stock3_volume=0),
        PhExperiment(well="A2", stock1_volume=0, stock2_volume=350, stock3_volume=0),
        # Add more experiments here as needed.
    ]


def load_batch_from_csv(csv_path: Path) -> list[PhExperiment]:
    batch: list[PhExperiment] = []
    with csv_path.open(newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            batch.append(
                PhExperiment(
                    well=row["well"],
                    stock1_volume=float(row["stock1_volume"]),
                    stock2_volume=float(row["stock2_volume"]),
                    stock3_volume=float(row["stock3_volume"]),
                )
            )
    return batch


def transfer_stock_to_batch(
    protocol: OTFlexProtocol,
    *,
    source_labware: str,
    source_well: str,
    volume_field: str,
    batch: Sequence[PhExperiment],
    pip_name: str = PIP_1000,
    sample_id: str | None = None,
) -> None:
    active = [exp for exp in batch if float(getattr(exp, volume_field)) > 0]
    if not active:
        return

    tracked_sample = sample_id or f"{source_labware}_{source_well}"
    used_tip = protocol.pick_up_tracked_tip(
        pip_name=pip_name,
        sample_id=tracked_sample,
        start_well=TIP_START_WELL,
    )
    print(f"{tracked_sample}: using shared tip {used_tip} for {len(active)} wells")
    try:
        for exp in active:
            volume = float(getattr(exp, volume_field))
            protocol.transfer_liquid(
                pip_name=pip_name,
                source_labware=source_labware,
                source_well=source_well,
                dest_labware=LW_TARGET_PLATE,
                dest_well=exp.well,
                volume=volume,
                source_top=-48,
                dest_top=0,
            )
    finally:
        protocol.drop_tip(pip_name=pip_name)


def measure_ph_placeholder(
    protocol: OTFlexProtocol,
    *,
    well: str,
    pip_name: str = PIP_1000,
    sample_volume_ul: float = 12,
    repeats: int = 1,
    reads_per_repeat: int = 3,
) -> list[float]:
    ph_values: list[float] = []
    for _ in range(repeats):
        used_tip = protocol.aliquot_to_target(
            pip_name=pip_name,
            source_labware=LW_TARGET_PLATE,
            source_well=well,
            dest_labware=LW_PH_UNIT,
            dest_well=PH_UNIT_WELL,
            volume=sample_volume_ul,
            sample_id=f"ph_{well}",
            start_well=TIP_START_WELL,
            source_top=-7,
            dest_top=-7,
        )
        print(f"pH placeholder {well}: tip {used_tip}")
        # Placeholder values replacing analyzer reads.
        ph_values.extend([float("nan")] * reads_per_repeat)

    return ph_values


def run_batch(protocol: OTFlexProtocol, batch: Sequence[PhExperiment]) -> list[list[float]]:
    transfer_stock_to_batch(
        protocol,
        source_labware=LW_VIAL_STOCK,
        source_well="A1",
        volume_field="stock1_volume",
        batch=batch,
    )
    transfer_stock_to_batch(
        protocol,
        source_labware=LW_VIAL_STOCK,
        source_well="B1",
        volume_field="stock2_volume",
        batch=batch,
    )
    transfer_stock_to_batch(
        protocol,
        source_labware=LW_VIAL_STOCK,
        source_well="A2",
        volume_field="stock3_volume",
        batch=batch,
    )

    results: list[list[float]] = []
    for exp in batch:
        print(f"--- Mixing and placeholder pH step for {exp.well} ---")
        protocol.mix(
            pip_name=PIP_1000,
            labware=LW_TARGET_PLATE,
            well=exp.well,
            volume=300,
            cycles=3,
            compound=f"mix_{exp.well}",
            mix_top=-7,
            start_well=TIP_START_WELL,
        )
        ph_list = measure_ph_placeholder(
            protocol,
            well=exp.well,
            repeats=1,
            reads_per_repeat=3,
        )
        results.append(ph_list)

    protocol.ot.home()
    return results


def save_results_csv(
    *,
    batch: Sequence[PhExperiment],
    results: Sequence[Sequence[float]],
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = output_dir / f"ph_results_{ts}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["well", "v_0.01M_HCl_acid", "v_0.1M_HOAc", "v_0.1M_NaOAc", "pH"])
        for exp, ph_list in zip(batch, results):
            for ph in ph_list:
                writer.writerow(
                    [exp.well, exp.stock1_volume, exp.stock2_volume, exp.stock3_volume, ph]
                )
    return csv_path


if __name__ == "__main__":
    protocol = OTFlexProtocol(simulation=False)
    try:
        # batch = build_batch()
        # # Example:
        batch = load_batch_from_csv(Path(r"C:\Users\sdl2\Documents\Code\Solid_dose_workflow\sdl2_solid_dose\workflow\test.csv"))
        results = run_batch(protocol, batch)
        print("Batch results:", results)
        out_csv = save_results_csv(
            batch=batch,
            results=results,
            output_dir=Path("results") / datetime.now().strftime("%Y%m%d"),
        )
        print(f"Saved results to: {out_csv}")
    finally:
        protocol.close()
