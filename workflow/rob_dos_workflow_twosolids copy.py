import time

from matterlab_balances import MTXPRBalanceDoors
from sdl2_solid_dose import BalanceProtocol, URController


DOSE_PLAN = [
	("A1", 15),
	("A5", 10),
]


def run_dose_plan(*, dose_plan: list[tuple[str, float]]) -> None:
	balance = BalanceProtocol()
	rob = URController()

	rob.home()
	rob.activate_gripper()

	# Move vial to balance once, then perform all dosing steps.
	time.sleep(1)
	balance.open_door(MTXPRBalanceDoors.RIGHT_OUTER)
	time.sleep(1)
	rob.vial_2_balance("A1")

	for head_location, target_weight_mg in dose_plan:
		head = balance.get_head_info(head_location)
		print(
			f"Using head {head_location}: {head['head_name']} -> {target_weight_mg} mg"
		)

		time.sleep(1)
		rob.dose_2_balance(head_location)

		balance.close_door(MTXPRBalanceDoors.RIGHT_OUTER)
		balance.auto_dose_from_head(
			head_location=head_location,
			target_weight_mg=target_weight_mg,
			validate_loaded_head=False,
		)

		# balance.open_door(MTXPRBalanceDoors.RIGHT_OUTER)
		time.sleep(1)
		rob.dose_balance_2_stock(head_location)

	# Move vial back after all powders are dosed.
	balance.open_door(MTXPRBalanceDoors.RIGHT_OUTER)
	time.sleep(1)
	rob.vial_2_OT("A1")


if __name__ == "__main__":
	run_dose_plan(dose_plan=DOSE_PLAN)

