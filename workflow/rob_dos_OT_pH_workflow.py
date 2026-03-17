import json
import time
import sys
import os
from pathlib import Path
from matterlab_balances import MTXPRBalance, MTXPRBalanceDoors
from sdl2_solid_dose import URController
from matterlab_balances.mt_balance import MTXPRBalanceDosingError, MTXPRBalanceRequestError
import time

BALANCE_IP = os.environ.get("BALANCE_IP")
BALANCE_PASSWORD = os.environ.get("BALANCE_PASSWORD")

substance_name = "Gum"
target_weight_mg = 30

balance = MTXPRBalance (host = BALANCE_IP, password = BALANCE_PASSWORD)
rob = URController()

# rob.home()
# rob.activate_gripper()
# rob.gripper_pos(rob.gripper_dist["open"]["dose"])
# rob.movej("safe_rack")
# balance.open_door(MTXPRBalanceDoors.RIGHT_OUTER)
# rob.home()
# rob.vial_2_balance()
# balance.close_door(MTXPRBalanceDoors.RIGHT_OUTER)
# rob.dose_2_balance()

# while True:
#     try:
#         balance.auto_dose(substance_name=substance_name, target_weight_mg=target_weight_mg)
#         break
#     except:
#         print("Auto-dose failed. Retrying...")
#         continue
    
for i in range(0,5):
    try:
        balance.auto_dose(substance_name=substance_name, target_weight_mg=target_weight_mg)
        print("Auto-dose completed successfully.")
        break
    except MTXPRBalanceDosingError as e:
        print(f"Auto-dose attempt {i+1} failed with error: {str(e)}")
        if i == 4:
            print("Max attempts reached. Auto-dose failed.")
            break
        continue
# try:
# 	balance.auto_dose(substance_name=substance_name, target_weight_mg=target_weight_mg)
# 	print("Auto-dose completed successfully.")
# except MTXPRBalanceDosingError as e:
# 	err_text = str(e)
# 	if "TareNegativeGrossWeight" in err_text:
# 		print("Negative gross weight detected. Re-zeroing and retrying once...")
# 		balance.zero()
# 		time.sleep(1)
# 		try:
# 			balance.auto_dose(substance_name=substance_name, target_weight_mg=target_weight_mg)
# 			print("Auto-dose completed successfully after re-zero.")
# 		except MTXPRBalanceRequestError as retry_err:
# 			print("Retry failed because the balance task is still blocked.")
# 			print("Clear/finish the current task on the balance UI, then run again.")
# 			raise
# 	else:
# 		raise
# balance.close_door(MTXPRBalanceDoors.RIGHT_OUTER)

# balance.open_door(MTXPRBalanceDoors.RIGHT_OUTER)
 
# rob.home()
# rob.activate_gripper()
# rob.vial_2_balance() 
# rob.dose_2_balance()
# rob.balance_2_home()


# rob.dosehead_2_balance()
#balance.zero()

# time.sleep(1)
# balance.open_door(MTXPRBalanceDoors.RIGHT_OUTER)
# rob.home_h()
# rob.home_2_balance()
# rob.balance_2_ot_2_home()

