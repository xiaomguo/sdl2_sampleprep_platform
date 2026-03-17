import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
from matterlab_opentrons import OpenTrons


class OTFlexProtocol:
    """OT Flex runtime: load deck config and execute high-level liquid-handling steps."""

    def __init__(
        self,
        simulation: bool = True,
        repo_root: Path | None = None,
        layout_relpath: str = "settings/opentrons/solide_liquid_hs_hplc_workflow_0308_layout.json",
        tip_state_relpath: str = "settings/opentrons/state/tip_tracking_demo.json",
        tiprack_nickname: str = "tip_1000_96_1",
    ):
        load_dotenv()
        self.simulation = simulation
        self.repo_root = (
            repo_root if repo_root is not None else Path(__file__).resolve().parents[3]
        )
        self.settings_dir = self.repo_root / "settings" / "opentrons"
        self.labware_dir = self.settings_dir / "labware"
        self.layout_path = self.repo_root / layout_relpath
        self.tip_state_path = self.repo_root / tip_state_relpath
        self.tiprack_nickname = tiprack_nickname

        self.layout = self._load_json(self.layout_path)
        self._validate_tip_status_json()
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
        self.ot.home()
        self.ot.load_trash_bin()

    def _load_json(self, path: Path) -> Dict:
        if not path.exists():
            raise FileNotFoundError(f"JSON file not found: {path}")
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _validate_tip_status_json(self) -> None:
        if not self.tip_state_path.exists():
            raise FileNotFoundError(
                f"Tip tracking JSON is required and was not found: {self.tip_state_path}"
            )

        loaded = self._load_json(self.tip_state_path)
        if "config" not in loaded or "tip_status" not in loaded["config"]:
            raise ValueError(
                f"Tip tracking JSON must contain config.tip_status: {self.tip_state_path}"
            )
        if "nickname" not in loaded:
            raise ValueError(
                f"Tip tracking JSON must contain nickname: {self.tip_state_path}"
            )

        tip_status = loaded["config"]["tip_status"]
        if not isinstance(tip_status, list) or len(tip_status) != 8:
            raise ValueError("config.tip_status must be an 8x12 matrix.")
        for row in tip_status:
            if not isinstance(row, list) or len(row) != 12:
                raise ValueError("config.tip_status must be an 8x12 matrix.")

    def _resolve_labware_definition(self, labware: Dict) -> Dict:
        lw = dict(labware)
        if not lw.get("ot_default", True):
            filename = lw.get("config_file")
            if not filename:
                raise ValueError(f"Missing config_file for custom labware: {lw['nickname']}")
            lw["config"] = self._load_json(self.labware_dir / filename)
            lw["config"] = self._sanitize_custom_load_name(lw["config"])
        else:
            lw["config"] = {}
        lw.pop("config_file", None)
        return lw

    def _sanitize_custom_load_name(self, labware_config: Dict) -> Dict:
        parameters = labware_config.get("parameters", {})
        load_name = parameters.get("loadName")
        if not isinstance(load_name, str):
            return labware_config

        # matterlab_opentrons uses parameters.loadName as a remote variable name.
        # Ensure it is a valid Python identifier to avoid remote NameError/SyntaxError.
        if load_name.isidentifier():
            return labware_config

        safe_name = re.sub(r"[^0-9a-zA-Z_]", "_", load_name)
        if not safe_name or safe_name[0].isdigit():
            safe_name = f"lw_{safe_name}"
        if not safe_name.isidentifier():
            safe_name = "lw_custom_labware"

        config_copy = json.loads(json.dumps(labware_config))
        config_copy.setdefault("parameters", {})["loadName"] = safe_name
        return config_copy

    def _load_labware_and_instrument(self) -> None:
        for labware in self.layout["labware"]:
            if labware["nickname"] == self.tiprack_nickname:
                self.ot.load_labware(self.tip_state_path)
                continue
            self.ot.load_labware(self._resolve_labware_definition(labware))

        for instrument in self.layout["instruments"]:
            self.ot.load_instrument(instrument)

    def load_module(
        self,
        *,
        nickname: str,
        module_name: str,
        location: str,
        adapter: Optional[str] = None,
    ) -> None:
        if adapter:
            self.ot.load_module(
                {
                    "nickname": nickname,
                    "module_name": module_name,
                    "location": location,
                    "adapter": adapter,
                }
            )
            return
        self.ot.invoke(
            f"{nickname} = protocol.load_module(module_name = '{module_name}', location = '{location}')"
        )

    def hs_latch_open(self, *, nickname: str) -> None:
        self.ot.hs_latch_open(nickname=nickname)

    def hs_latch_close(self, *, nickname: str) -> None:
        self.ot.hs_latch_close(nickname=nickname)

    def hs_set_and_wait_shake_speed(self, *, nickname: str, rpm: int) -> None:
        self.ot.hs_set_and_wait_shake_speed(nickname=nickname, rpm=rpm)

    def hs_deactivate_shaker(self, *, nickname: str) -> None:
        self.ot.hs_deactivate_shaker(nickname=nickname)

    def hs_set_and_wait_temperature(self, *, nickname: str, celsius: float) -> None:
        self.ot.hs_set_and_wait_temperature(nickname=nickname, celsius=celsius)

    def hs_set_target_temperature(self, *, nickname: str, celsius: float) -> None:
        self.ot.hs_set_target_temperature(nickname=nickname, celsius=celsius)

    def hs_wait_for_temperature(self, *, nickname: str) -> None:
        self.ot.hs_wait_for_temperature(nickname=nickname)

    def hs_deactivate_heater(self, *, nickname: str) -> None:
        self.ot.hs_deactivate_heater(nickname=nickname)

    def hs_deactivate(self, *, nickname: str) -> None:
        self.ot.hs_deactivate(nickname=nickname)

    def move_labware_with_gripper(self, *, labware_nickname: str, new_location: str) -> None:
        self.ot.move_labware_w_gripper(
            labware_nickname=labware_nickname,
            new_location=new_location,
        )

    def move_labware_with_gripper_to_module(
        self, *, labware_nickname: str, module_nickname: str
    ) -> None:
        self.ot.invoke(
            f"protocol.move_labware(labware = {labware_nickname}, "
            f"new_location = {module_nickname}, use_gripper = True)"
        )

    def gripper_is_attached(self) -> bool:
        try:
            return bool(self.ot.gripper_is_attached())
        except Exception:
            self._ensure_gripper_context_compat()
            return self._invoke_bool("hardware.has_gripper()")

    def gripper_close_jaw(self) -> None:
        try:
            self.ot.gripper_close_jaw()
        except Exception:
            self._ensure_gripper_context_compat()
            self.ot.invoke("assert hardware.has_gripper(), 'No gripper attached'")
            self.ot.invoke("hardware.grip(sync=True)")

    def gripper_open_jaw(self) -> None:
        try:
            self.ot.gripper_open_jaw()
        except Exception:
            self._ensure_gripper_context_compat()
            self.ot.invoke("assert hardware.has_gripper(), 'No gripper attached'")
            self.ot.invoke("hardware.ungrip(sync=True)")

    def gripper_jaw_width(self) -> float:
        try:
            return float(self.ot.gripper_jaw_width())
        except Exception:
            self._ensure_gripper_context_compat()
            return self._invoke_float("float(gripper.state_jaw_width_mm)")

    def gripper_jaw_limits(self) -> Dict[str, float]:
        try:
            limits = self.ot.gripper_jaw_limits()
            return {"min": float(limits["min"]), "max": float(limits["max"])}
        except Exception:
            self._ensure_gripper_context_compat()
            min_w = self._invoke_float("float(gripper.config_jaw_mm['min'])")
            max_w = self._invoke_float("float(gripper.config_jaw_mm['max'])")
            return {"min": min_w, "max": max_w}
        

    def gripper_move_to_absolute(
        self,
        *,
        x: float,
        y: float,
        z: float,
        speed: Optional[float] = None,
    ) -> None:
        try:
            self.ot.gripper_move_to_absolute(x=x, y=y, z=z, speed=speed)
        except Exception:
            self._ensure_gripper_context_compat()
            self.ot.invoke(f"location = Point({x}, {y}, {z})")
            if speed is None:
                self.ot.invoke("hardware.move_to(mount=gripper_mount, abs_position=location)")
            else:
                self.ot.invoke(
                    f"hardware.move_to(mount=gripper_mount, abs_position=location, speed={speed})"
                )

    def _ensure_gripper_context_compat(self) -> None:
        """Initialize remote `hardware`/`gripper` handles with API-version-compatible access."""
        self.ot.invoke(
            "if hasattr(protocol, '_core_get_hardware'):\n"
            "    hardware = protocol._core_get_hardware()\n"
            "elif hasattr(protocol, '_core') and hasattr(protocol._core, 'get_hardware'):\n"
            "    hardware = protocol._core.get_hardware()\n"
            "elif hasattr(protocol, '_hw_manager') and hasattr(protocol._hw_manager, 'hardware'):\n"
            "    hardware = protocol._hw_manager.hardware\n"
            "else:\n"
            "    raise AttributeError('No compatible hardware accessor found on protocol context')"
        )
        self.ot.invoke("hardware.cache_instruments() if hasattr(hardware, 'cache_instruments') else None")
        self.ot.invoke("from opentrons import types as _ot_types")
        self.ot.invoke(
            "gripper_mount = getattr(getattr(_ot_types, 'OT3Mount', object), 'GRIPPER', None)"
        )
        self.ot.invoke(
            "gripper_mount = gripper_mount or getattr(getattr(_ot_types, 'Mount', object), 'GRIPPER', None)"
        )
        self.ot.invoke("gripper = hardware._gripper_handler.get_gripper() if hardware.has_gripper() else None")

    def _invoke_scalar(self, expression: str) -> str:
        raw = self.ot.invoke(expression)
        lines = [line for line in raw.strip().split("\n") if line.strip()]
        if not lines:
            raise RuntimeError(f"Empty response for remote expression: {expression}")
        return lines[-1].strip()

    def _invoke_bool(self, expression: str) -> bool:
        return self._invoke_scalar(expression).lower() == "true"

    def _invoke_float(self, expression: str) -> float:
        return float(self._invoke_scalar(expression))

    def move_gantry_to_absolute(
        self,
        *,
        pip_name: str,
        x: float,
        y: float,
        z: float,
        reference: Optional[str] = None,
        speed: Optional[float] = None,
        force_direct: Optional[bool] = None,
        minimum_z_height: Optional[float] = None,
    ) -> None:
        """Move pipette gantry to absolute XYZ using deck or slot reference coordinates."""
        self.ot.get_location_absolute(x=x, y=y, z=z, reference=reference)
        self.ot.move_to_pip_advanced(
            pip_name=pip_name,
            speed=speed,
            force_direct=force_direct,
            minimum_z_height=minimum_z_height,
        )

    def move_pipette_to_well(
        self,
        *,
        pip_name: str,
        labware: str,
        well: str,
        top: float = 0,
        bottom: float = 0,
        center: float = 0,
        speed: Optional[float] = None,
        force_direct: Optional[bool] = None,
        minimum_z_height: Optional[float] = None,
    ) -> None:
        """Move a pipette to a specific well position in loaded labware."""
        self.ot.get_location_from_labware(
            labware_nickname=labware,
            position=well,
            top=top,
            bottom=bottom,
            center=center,
        )
        self.ot.move_to_pip_advanced(
            pip_name=pip_name,
            speed=speed,
            force_direct=force_direct,
            minimum_z_height=minimum_z_height,
        )

    def move_pipette_relative_z(
        self,
        *,
        pip_name: str,
        dz: float,
        speed: Optional[float] = None,
        force_direct: Optional[bool] = None,
        minimum_z_height: Optional[float] = None,
    ) -> None:
        """Move current pipette location by relative Z offset (mm)."""
        self.ot.invoke(f"location = location.move(Point(0, 0, {dz}))")
        self.ot.move_to_pip_advanced(
            pip_name=pip_name,
            speed=speed,
            force_direct=force_direct,
            minimum_z_height=minimum_z_height,
        )

    def move_pipette_relative_xyz(
        self,
        *,
        pip_name: str,
        dx: float = 0,
        dy: float = 0,
        dz: float = 0,
        speed: Optional[float] = None,
        force_direct: Optional[bool] = None,
        minimum_z_height: Optional[float] = None,
    ) -> None:
        """Move current pipette location by relative XYZ offsets (mm)."""
        self.ot.invoke(f"location = location.move(Point({dx}, {dy}, {dz}))")
        self.ot.move_to_pip_advanced(
            pip_name=pip_name,
            speed=speed,
            force_direct=force_direct,
            minimum_z_height=minimum_z_height,
        )

    def manual_gripper_pick_place_absolute(
        self,
        *,
        pick_xyz: tuple[float, float, float],
        place_xyz: tuple[float, float, float],
        safe_z: float = 250.0,
        speed: Optional[float] = None,
    ) -> None:
        pick_x, pick_y, pick_z = pick_xyz
        place_x, place_y, place_z = place_xyz

        self.gripper_open_jaw()
        self.gripper_move_to_absolute(x=pick_x, y=pick_y, z=safe_z, speed=speed)
        self.gripper_move_to_absolute(x=pick_x, y=pick_y, z=pick_z, speed=speed)
        self.gripper_close_jaw()
        self.gripper_move_to_absolute(x=pick_x, y=pick_y, z=safe_z, speed=speed)

        self.gripper_move_to_absolute(x=place_x, y=place_y, z=safe_z, speed=speed)
        self.gripper_move_to_absolute(x=place_x, y=place_y, z=place_z, speed=speed)
        self.gripper_open_jaw()
        self.gripper_move_to_absolute(x=place_x, y=place_y, z=safe_z, speed=speed)

    def _pick_tip(
        self,
        pip_name: str,
        tiprack_nickname: str,
        start_well: str = "A1",
        sample_id: Optional[str] = None,
    ) -> str:
        return self.ot.pick_up_next_available_tip(
            pip_name=pip_name,
            tiprack_nickname=tiprack_nickname,
            sample_id=sample_id,
            start_well=start_well,
        )

    def pick_up_tracked_tip(
        self,
        *,
        pip_name: str,
        tiprack_nickname: Optional[str] = None,
        start_well: str = "A1",
        sample_id: Optional[str] = None,
    ) -> str:
        tiprack = tiprack_nickname or self.tiprack_nickname
        return self._pick_tip(
            pip_name=pip_name,
            tiprack_nickname=tiprack,
            start_well=start_well,
            sample_id=sample_id,
        )

    def aspirate_from(
        self,
        *,
        pip_name: str,
        labware: str,
        well: str,
        volume: float,
        top: float = 0,
        bottom: float = 0,
        center: float = 0,
    ) -> None:
        self.ot.get_location_from_labware(
            labware_nickname=labware,
            position=well,
            top=top,
            bottom=bottom,
            center=center,
        )
        self.ot.aspirate(pip_name=pip_name, volume=volume)

    def dispense_to(
        self,
        *,
        pip_name: str,
        labware: str,
        well: str,
        volume: float,
        top: float = 0,
        bottom: float = 0,
        center: float = 0,
    ) -> None:
        self.ot.get_location_from_labware(
            labware_nickname=labware,
            position=well,
            top=top,
            bottom=bottom,
            center=center,
        )
        self.ot.dispense(pip_name=pip_name, volume=volume)

    def transfer_liquid(
        self,
        *,
        pip_name: str,
        source_labware: str,
        source_well: str,
        dest_labware: str,
        dest_well: str,
        volume: float,
        source_top: float = 0,
        source_bottom: float = 0,
        source_center: float = 0,
        dest_top: float = 0,
        dest_bottom: float = 0,
        dest_center: float = 0,
    ) -> None:
        self.aspirate_from(
            pip_name=pip_name,
            labware=source_labware,
            well=source_well,
            volume=volume,
            top=source_top,
            bottom=source_bottom,
            center=source_center,
        )
        self.dispense_to(
            pip_name=pip_name,
            labware=dest_labware,
            well=dest_well,
            volume=volume,
            top=dest_top,
            bottom=dest_bottom,
            center=dest_center,
        )

    def drop_tip(self, *, pip_name: str) -> None:
        self.ot.drop_tip(pip_name=pip_name)

    def aliquot_to_target(
        self,
        *,
        pip_name: str,
        source_labware: str,
        source_well: str,
        dest_labware: str,
        dest_well: str,
        volume: float,
        tiprack_nickname: Optional[str] = None,
        sample_id: Optional[str] = None,
        start_well: str = "A1",
        source_top: float = 0,
        source_bottom: float = 0,
        source_center: float = 0,
        dest_top: float = 0,
        dest_bottom: float = 0,
        dest_center: float = 0,
    ) -> str:
        tiprack = tiprack_nickname or self.tiprack_nickname
        used_tip = self.pick_up_tracked_tip(
            pip_name=pip_name,
            tiprack_nickname=tiprack,
            start_well=start_well,
            sample_id=sample_id,
        )
        self.transfer_liquid(
            pip_name=pip_name,
            source_labware=source_labware,
            source_well=source_well,
            dest_labware=dest_labware,
            dest_well=dest_well,
            volume=volume,
            source_top=source_top,
            source_bottom=source_bottom,
            source_center=source_center,
            dest_top=dest_top,
            dest_bottom=dest_bottom,
            dest_center=dest_center,
        )
        self.drop_tip(pip_name=pip_name)
        return used_tip

    def transfer(
        self,
        *,
        pip_name: str,
        source_labware: str,
        source_well: str,
        dest_labware: str,
        dest_well: str,
        volume: float,
        tiprack_nickname: Optional[str] = None,
        compound: Optional[str] = None,
        source_top: float = -20,
        dest_top: float = 1,
        start_well: str = "A1",
    ) -> str:
        tiprack = tiprack_nickname or self.tiprack_nickname
        used_tip = self._pick_tip(
            pip_name=pip_name,
            tiprack_nickname=tiprack,
            start_well=start_well,
            sample_id=compound,
        )
        print(
            f"Transfer {compound or ''}: {source_labware}:{source_well} -> "
            f"{dest_labware}:{dest_well}, vol={volume} uL, tip={used_tip}"
        )

        self.ot.get_location_from_labware(source_labware, position=source_well, top=source_top)
        self.ot.aspirate(pip_name=pip_name, volume=volume)

        self.ot.get_location_from_labware(dest_labware, position=dest_well, top=dest_top)
        self.ot.dispense(pip_name=pip_name, volume=volume)
        self.ot.drop_tip(pip_name=pip_name)
        return used_tip

    def transfer_and_mix(
        self,
        *,
        pip_name: str,
        source_labware: str,
        source_well: str,
        dest_labware: str,
        dest_well: str,
        transfer_volume: float,
        mix_volume: float,
        mix_cycles: int,
        tiprack_nickname: Optional[str] = None,
        compound: Optional[str] = None,
        source_top: float = -20,
        dest_top: float = 1,
        mix_top: float = -4,
        start_well: str = "A1",
    ) -> str:
        tiprack = tiprack_nickname or self.tiprack_nickname
        used_tip = self._pick_tip(
            pip_name=pip_name,
            tiprack_nickname=tiprack,
            start_well=start_well,
            sample_id=compound,
        )
        print(
            f"Transfer+Mix {compound or ''}: {source_labware}:{source_well} -> "
            f"{dest_labware}:{dest_well}, transfer={transfer_volume} uL, "
            f"mix={mix_volume} uL x{mix_cycles}, tip={used_tip}"
        )

        self.ot.get_location_from_labware(source_labware, position=source_well, top=source_top)
        self.ot.aspirate(pip_name=pip_name, volume=transfer_volume)

        self.ot.get_location_from_labware(dest_labware, position=dest_well, top=dest_top)
        self.ot.dispense(pip_name=pip_name, volume=transfer_volume)

        for _ in range(mix_cycles):
            self.ot.get_location_from_labware(dest_labware, position=dest_well, top=mix_top)
            self.ot.aspirate(pip_name=pip_name, volume=mix_volume)
            self.ot.dispense(pip_name=pip_name, volume=mix_volume)

        self.ot.drop_tip(pip_name=pip_name)
        return used_tip

    def mix(
        self,
        *,
        pip_name: str,
        labware: str,
        well: str,
        volume: float,
        cycles: int,
        tiprack_nickname: Optional[str] = None,
        compound: Optional[str] = None,
        mix_top: float = -4,
        start_well: str = "A1",
    ) -> str:
        tiprack = tiprack_nickname or self.tiprack_nickname
        used_tip = self._pick_tip(
            pip_name=pip_name,
            tiprack_nickname=tiprack,
            start_well=start_well,
            sample_id=compound,
        )
        print(
            f"Mix {compound or ''}: {labware}:{well}, vol={volume} uL, "
            f"cycles={cycles}, tip={used_tip}"
        )
        for _ in range(cycles):
            self.ot.get_location_from_labware(labware, position=well, top=mix_top)
            self.ot.aspirate(pip_name=pip_name, volume=volume)
            self.ot.dispense(pip_name=pip_name, volume=volume)
        self.ot.drop_tip(pip_name=pip_name)
        return used_tip

    def execute_plan(self, steps: List[Dict]) -> None:
        for idx, step in enumerate(steps, start=1):
            action = step.get("action")
            if action == "transfer":
                self.transfer(
                    pip_name=step["pip_name"],
                    source_labware=step["source_labware"],
                    source_well=step["source_well"],
                    dest_labware=step["dest_labware"],
                    dest_well=step["dest_well"],
                    volume=step["volume"],
                    tiprack_nickname=step.get("tiprack_nickname"),
                    compound=step.get("compound"),
                    source_top=step.get("source_top", -20),
                    dest_top=step.get("dest_top", 1),
                    start_well=step.get("start_well", "A1"),
                )
            elif action == "transfer_and_mix":
                self.transfer_and_mix(
                    pip_name=step["pip_name"],
                    source_labware=step["source_labware"],
                    source_well=step["source_well"],
                    dest_labware=step["dest_labware"],
                    dest_well=step["dest_well"],
                    transfer_volume=step["transfer_volume"],
                    mix_volume=step["mix_volume"],
                    mix_cycles=step["mix_cycles"],
                    tiprack_nickname=step.get("tiprack_nickname"),
                    compound=step.get("compound"),
                    source_top=step.get("source_top", -20),
                    dest_top=step.get("dest_top", 1),
                    mix_top=step.get("mix_top", -4),
                    start_well=step.get("start_well", "A1"),
                )
            elif action == "mix":
                self.mix(
                    pip_name=step["pip_name"],
                    labware=step["labware"],
                    well=step["well"],
                    volume=step["volume"],
                    cycles=step["cycles"],
                    tiprack_nickname=step.get("tiprack_nickname"),
                    compound=step.get("compound"),
                    mix_top=step.get("mix_top", -4),
                    start_well=step.get("start_well", "A1"),
                )
            else:
                raise ValueError(f"Unsupported action '{action}' at step {idx}.")

    def run_default_plan(self) -> None:
        default_steps = [
            {
                "action": "transfer",
                "pip_name": "p1000",
                "compound": "buffer_A",
                "source_labware": "al_plate_24",
                "source_well": "A1",
                "dest_labware": "plate_96_1",
                "dest_well": "A1",
                "volume": 200,
            },
            {
                "action": "mix",
                "pip_name": "p1000",
                "compound": "buffer_A",
                "labware": "plate_96_1",
                "well": "A1",
                "volume": 100,
                "cycles": 2,
            },
        ]
        self.execute_plan(default_steps)
        self.ot.home()

    def close(self) -> None:
        self.ot.close_session()

    def close_without_home(self) -> None:
        """Close transport/session without issuing protocol.home()."""
        disconnect = getattr(self.ot, "_disconnect", None)
        if callable(disconnect):
            disconnect()
            return
        raise RuntimeError("Underlying OpenTrons client does not support close_without_home.")
