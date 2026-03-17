from dotenv import load_dotenv
import socket
import time
import os

load_dotenv()

def send_gripper_command(command, ip=None, port=63352):
    if ip is None:
        ip = os.environ.get("ROBOT_IP")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(5)
        try:
            s.connect((ip, port))
            s.sendall(command.encode('utf-8') + b'\n')
            data = s.recv(1024)
            print(f"[SENT] {command}")
            print(f"[RECV] {data.decode(errors='ignore')}")
        except Exception as e:
            print("[ERROR]", e)


# send_gripper_command('SET ACT 1')
# time.sleep(1)


def percentage_to_socket_value(percent):
    return int(max(0, min(100, percent)) * 2.55)

def main():
    print("== Gripper Socket Control ==")
    print("Initializing gripper...\n")

    # Step 1: Activate gripper
    send_gripper_command("SET ACT 1")
    time.sleep(0.5)

    # Step 2: Set Gripper to Go (Start Action Mode)
    send_gripper_command("SET GTO 1")
    time.sleep(0.5)

    print("\nGripper ready. Type a percentage (0–100) to move.")
    print("Type 'exit' to quit.\n")

    while True:
        user_input = input("Enter gripper position percentage (e.g. 84, 88): ")
        if user_input.strip().lower() in ['exit', 'quit']:
            break
        try:
            percent = float(user_input)
            pos_val = percentage_to_socket_value(percent)
            print(f"→ Sending gripper position {pos_val} for {percent:.2f}%")
            send_gripper_command(f"SET POS {pos_val} GTO01")
            time.sleep(0.5)  # Give time for motion to complete
        except ValueError:
            print("⚠️ Please enter a valid number or 'exit'.")

if __name__ == "__main__":
    main()