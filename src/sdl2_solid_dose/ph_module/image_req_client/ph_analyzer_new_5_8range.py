"""
pH Analyzer Class - Complete pH testing system in one class.

"""

import socket
import tempfile
from pathlib import Path
from time import sleep
from typing import Optional, Tuple

try:
    from .ph_color_reader_new_xg_5_8range import ph_from_image
except ImportError:
    from ph_color_reader_new_xg_5_8range import ph_from_image

# ============================================================
# LED COLOR CONFIGURATION (CHANGE THESE VALUES)
# ============================================================
# LED_COLOR_ENABLED = True   # Set to True to change LED color
# LED_COLOR_R = 0         # Red (0-255)
# LED_COLOR_G = 0       # Green (0-255)
# LED_COLOR_B = 0        # Blue (0-255)



class PHAnalyzer:
    def __init__(self, server_ip="172.31.60.12", port=2222, save_raw_images=True):
        self.server_ip = server_ip
        self.port = port
        self.socket = None
        self.connected = False
        self.save_raw_images = save_raw_images


    def connect(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(30)
            self.socket.connect((self.server_ip, self.port))
            self.connected = True
            print(f"[pHAnalyzer] Connected to {self.server_ip}")
            return True
        except Exception as e:
            print(f"[pHAnalyzer] Connection failed: {e}")
            self.connected = False
            return False

    def disconnect(self):
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
            self.socket = None
            self.connected = False


    # SOCKET HELPERS

    def _send_string(self, msg):
        if not msg.endswith("\n"):
            msg += "\n"
        self.socket.sendall(msg.encode("utf-8"))

    def _recv_string(self):
        data = b""
        while b"\n" not in data:
            chunk = self.socket.recv(1024)
            if not chunk:
                return None
            data += chunk
        return data.decode("utf-8").strip()

    def _recv_file(self, size):
        data = b""
        while len(data) < size:
            data += self.socket.recv(4096)
        return data


    # CAMERA

    def request_photo(self, light_setting=(10, 10, 10)) -> Optional[Tuple[str, str]]:
        """
        Takes a single photo under the specified lighting condition.
        If light_setting is provided (tuple of (R,G,B)), sets the LED before taking the photo.
        Returns (temp_file_path, original_filename) or None on failure.
        """
        if not self.connected:
            if not self.connect():
                return None

        if light_setting is not None:
            try:
                r, g, b = light_setting
                self.change_led_color(r, g, b)
            except Exception as _led_err:
                print(f"[pHAnalyzer] LED change skipped: {_led_err}")

        print(f"[pHAnalyzer] Capturing photo...")
        self._send_string("TAKE_PHOTO")
        sleep(5)

        filename = self._recv_string()
        if not filename:
            print("[pHAnalyzer] Failed to receive filename")
            return None

        self._send_string(filename)

        size = int(self._recv_string())
        self._send_string(str(size))

        data = self._recv_file(size)

        if self.save_raw_images:
            output_dir = Path(__file__).parent / "output_images"
            output_dir.mkdir(parents=True, exist_ok=True)
            path = output_dir / filename
            path.write_bytes(data)
            print(f"[pHAnalyzer] Raw image saved to {path}")
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(data)
            temp_path = tmp.name

        # Return tuple: (temp_file_path, original_filename)
        return (str(temp_path), filename)


    # ANALYSIS

    def analyze_image(self, image_path, original_filename=None):
        try:
            out_dir = Path(__file__).parent / "output_images"
            out_dir.mkdir(parents=True, exist_ok=True)

            print("[pHAnalyzer] Analyzing pH...")
            result = ph_from_image(
                str(image_path),
                output_dir=str(out_dir),
                original_filename=original_filename
            )

            return result

        except Exception as e:
            print(f"[pHAnalyzer] Analysis failed: {e}")
            return None


    # ONE-SHOT API

    def read_ph(self, well=None):
        result_tuple = self.request_photo()
        if not result_tuple:
            return None

        image_path, original_filename = result_tuple

        # If well is provided, add it to the filename
        if well:
            # Insert well before file extension
            stem, ext = Path(original_filename).stem, Path(original_filename).suffix
            original_filename = f"{stem}_{well}{ext}"

        ph = self.analyze_image(image_path, original_filename)
        if ph is not None:
            print(f"pH: {ph}")
        return ph


    # MOTOR

    def dispense_strip(self):
        if not self.connected:
            if not self.connect():
                return False

        try:
            print("[pHAnalyzer] Dispensing strip...")
            self._send_string("RUN_MOTOR")
            resp = self.socket.recv(1024).decode("utf-8")
            return "COMPLETE" in resp
        except Exception as e:
            print(f"[pHAnalyzer] Motor error: {e}")
            return False


    # LED COLOR

    def change_led_color(self, r, g, b):
        """
        Change LED color on the server.
        
        Args:
            r: Red value (0-255)
            g: Green value (0-255)
            b: Blue value (0-255)
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.connected:
            if not self.connect():
                return False

        try:
            if not all(0 <= val <= 255 for val in (r, g, b)):
                print(f"[pHAnalyzer] Invalid RGB values: {r},{g},{b}. Must be 0-255")
                return False
                
            print(f"[pHAnalyzer] Requesting LED color change to ({r}, {g}, {b})...")
            self._send_string("CHANGE_COLOR")
            
            # Wait for server to request RGB values (server may not send newline)
            response = self.socket.recv(1024).decode("utf-8").strip()
            if response != "PLEASE SEND RGB":
                print(f"[pHAnalyzer] Unexpected server response: {response}")
                return False
            
            # Send RGB values
            rgb_string = f"{r},{g},{b}"
            self._send_string(rgb_string)
            
            # Wait for confirmation (server may not send newline)
            confirmation = self.socket.recv(1024).decode("utf-8").strip()
            if confirmation == "COLOR_CHANGED":
                print(f"[pHAnalyzer] LED color successfully changed")
                return True
            else:
                print(f"[pHAnalyzer] Color change failed: {confirmation}")
                return False
                
        except Exception as e:
            print(f"[pHAnalyzer] LED color change error: {e}")
            return False

    # CONTEXT MANAGER

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        return False


# Backward-compatible alias used by existing scripts.
pHAnalyzer = PHAnalyzer
