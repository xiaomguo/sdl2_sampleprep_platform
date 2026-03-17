
import json
import os
import time
from pathlib import Path
from typing import Any, Dict

from matterlab_balances import MTXPRBalance, MTXPRBalanceDoors
from matterlab_balances.mt_balance import MTXPRBalanceDosingError


class BalanceProtocol:
    """Mid-level balance runtime: load dosing-head config and execute dosing by head location."""

    def __init__(
        self,
        *,
        repo_root: Path | None = None,
        heads_config_relpath: str = "settings/robot/dosing_heads.json",
        balance_ip: str | None = None,
        balance_password: str | None = None,
    ):
        self.repo_root = (
            repo_root if repo_root is not None else Path(__file__).resolve().parents[3]
        )
        self.heads_config_path = self.repo_root / heads_config_relpath
        self.balance_ip = balance_ip or os.environ.get("BALANCE_IP")
        self.balance_password = balance_password or os.environ.get("BALANCE_PASSWORD")

        self._heads = self._load_heads(self.heads_config_path)
        self.balance = self._connect_balance()

    def _load_heads(self, config_path: Path) -> Dict[str, Dict[str, Any]]:
        if not config_path.exists():
            raise FileNotFoundError(f"Dosing head config not found: {config_path}")

        with config_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise ValueError(f"Expected object mapping in config: {config_path}")

        return data

    def _connect_balance(self) -> MTXPRBalance:
        if not self.balance_ip:
            raise ValueError("BALANCE_IP is not set.")
        if not self.balance_password:
            raise ValueError("BALANCE_PASSWORD is not set.")
        return MTXPRBalance(host=self.balance_ip, password=self.balance_password)

    def get_head_info(self, location: str) -> Dict[str, Any]:
        info = self._heads.get(location)
        if info is None:
            raise KeyError(
                f"Head location '{location}' not found in {self.heads_config_path.name}."
            )
        if not isinstance(info, dict):
            raise ValueError(f"Head info for '{location}' must be an object.")

        required = ["head_name", "substance_name", "powder"]
        missing = [key for key in required if not info.get(key)]
        if missing:
            raise ValueError(f"Head '{location}' missing required keys: {missing}")
        return info

    def get_substance_name(self, location: str) -> str:
        return str(self.get_head_info(location)["substance_name"])

    def open_door(self, door: MTXPRBalanceDoors) -> None:
        self.balance.open_door(door)

    def close_door(self, door: MTXPRBalanceDoors) -> None:
        self.balance.close_door(door)

    def read_dosing_head(self) -> Any:
        """Read currently mounted dosing-head payload from the balance."""
        return self.balance.read_dosing_head()

    def get_substance_name_from_balance(self) -> str:
        """Extract substance_name from balance.read_dosing_head() response payload."""
        payload = self.read_dosing_head()
        if isinstance(payload, dict):
            details = payload.get("dosing_head_info_details")
            if isinstance(details, dict):
                substance_name = details.get("substance_name")
                if substance_name:
                    return str(substance_name)
            direct_name = payload.get("substance_name")
            if direct_name:
                return str(direct_name)

        raise ValueError(
            "Could not read substance_name from balance dosing-head payload. "
            f"Payload: {payload}"
        )

    def validate_loaded_head(self, *, head_location: str) -> str:
        """Validate balance-reported head identity against config for a location."""
        expected = str(self.get_head_info(head_location)["head_name"])
        actual = self.read_dosing_head()

        expected_norm = expected.strip().lower()
        actual_norm = actual.strip().lower()
        if expected_norm != actual_norm:
            raise ValueError(
                "Loaded dosing head does not match expected config. "
                f"location={head_location}, expected='{expected}', actual='{actual}'"
            )
        return actual

    def auto_dose_from_head(
        self,
        *,
        head_location: str,
        target_weight_mg: float,
        validate_loaded_head: bool = True,
    ) -> None:
        """Auto-dose using balance-reported substance name, with config fallback."""
        if validate_loaded_head:
            self.validate_loaded_head(head_location=head_location)

        try:
            substance_name = self.get_substance_name_from_balance()
        except ValueError:
            # Fallback for environments where head payload lacks substance_name.
            substance_name = self.get_substance_name(head_location)
        self.balance.auto_dose(
            substance_name=substance_name,
            target_weight_mg=target_weight_mg,
        )

    def auto_dose_from_head_with_retry(
        self,
        *,
        head_location: str,
        target_weight_mg: float,
        max_attempts: int = 5,
        retry_delay_s: float = 0.0,
        validate_loaded_head: bool = True,
    ) -> bool:
        """Auto-dose with retry support.

        Args:
            head_location: Dosing-head position key from dosing_heads.json (e.g. "A1").
            target_weight_mg: Target dose in milligrams.
            max_attempts: Number of times to try auto-dose.
            retry_delay_s: Optional delay between failed attempts.
            validate_loaded_head: Whether to validate loaded head before dosing.

        Returns:
            True on success, False after all attempts fail.
        """
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")

        for i in range(max_attempts):
            try:
                self.auto_dose_from_head(
                    head_location=head_location,
                    target_weight_mg=target_weight_mg,
                    validate_loaded_head=validate_loaded_head,
                )
                print("Auto-dose completed successfully.")
                return True
            except MTXPRBalanceDosingError as e:
                print(f"Auto-dose attempt {i+1} failed with error: {str(e)}")
                if i == max_attempts - 1:
                    print("Max attempts reached. Auto-dose failed.")
                    return False
                if retry_delay_s > 0:
                    time.sleep(retry_delay_s)

        return False
