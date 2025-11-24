import subprocess, sys
from pathlib import Path
import pytesseract
import threading
import time
import unicodedata
from colorama import Fore, Style, init as colorama_init
import uiautomator2 as u2
import xml.etree.ElementTree as ET
from flask import Flask, request, jsonify
import logging
import os
import queue

colorama_init(autoreset=True)

SIMPLE_LOG = True
TAP_INPUT_ID = (600, 260)
TAP_LUPA = (850, 350)
TAP_CLOSE_VERIF = (960, 225)
TAP_TENTUKAN = (640, 450)
TAP_BACK = (65, 35)
OCR_AREA = (515, 230, 755, 275)
OCR_AREA_2 = (360, 220, 900, 400)

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(r.stderr.strip() or "Command failed")
    return r.stdout.strip()

def ocr_area(driver, area):
    try:
        screenshot = driver.screenshot(format='pillow')
        x1, y1, x2, y2 = area
        cropped = screenshot.crop((x1, y1, x2, y2))
        return pytesseract.image_to_string(cropped, lang='eng').strip()
    except Exception as e:
        return f"Error OCR: {str(e)}"

def normalize_text(text):
    normalized = unicodedata.normalize('NFKD', text)
    return normalized.replace('ﬁ', 'fi').replace('ﬂ', 'fl')

def dump_xml_text(driver):
    try:
        xml_content = driver.dump_hierarchy()
        root = ET.fromstring(xml_content)
        texts = []
        for elem in root.iter():
            text = elem.get('text', '')
            content_desc = elem.get('content-desc', '')
            if text:
                texts.append(text)
            if content_desc:
                texts.append(content_desc)
        return ' '.join(texts)
    except Exception as e:
        return f"Error XML: {str(e)}"

def finalize_check(user_id, driver, simple_log, running, status_name, return_status=False):
    try:
        driver.click(*TAP_INPUT_ID)
        time.sleep(0.3)
        focused = driver(focused=True)
        is_edit = focused.exists and ("EditText" in focused.info.get("className", "") or "TextInput" in focused.info.get("className", "") or focused.info.get("editable") is True)
        if is_edit:
            if not simple_log:
                print(f"[ACTION] EditText terdeteksi! Proses selesai.")
        else:
            if not simple_log:
                print(f"[INFO] EditText tidak terdeteksi setelah tap input ID")
        if return_status:
            return status_name
        running[0] = False
        sys.exit(0)
    except Exception as e:
        if not simple_log:
            print(f"[ERROR] Gagal finalisasi: {str(e)}")
        if return_status:
            return status_name
        running[0] = False
        sys.exit(0)

def check_keywords(text, user_id, driver, simple_log, running, return_status=False):
    normalized_text = normalize_text(text.lower())
    normalized_no_space = normalized_text.replace(' ', '').replace('\n', '').replace('\t', '')
    
    keywords_verif = ['verifikasigoogle', 'verifikasigoog', 'verifikasigoog1e']
    detected_verif = any(keyword in normalized_no_space for keyword in keywords_verif) or 'verifikasi' in normalized_text and 'google' in normalized_text
    detected_error = 'sistem error' in normalized_text or 'sistemerror' in normalized_no_space
    detected_polos = 'anda belum menghubungkan' in normalized_text or 'andabelummenghubungkan' in normalized_no_space
    detected_family = 'kepala family' in normalized_text or 'kepalafamily' in normalized_no_space or 'sandi anggota' in normalized_text or 'sandianggota' in normalized_no_space
    detected_belum_sandi = 'anda belum mengatur kata sandi' in normalized_text or 'andabelummengaturkatasandi' in normalized_no_space
    detected_tidak_ada = 'pengguna ini tidak ada' in normalized_text or 'penggunainitidakada' in normalized_no_space
    detected_perbarui = '278' in normalized_text or 'harap perbarui ke versi baru' in normalized_text or 'harapperbaruikeversibaru' in normalized_no_space
    
    if detected_polos:
        try:
            driver.click(*TAP_BACK)
            if not simple_log:
                print(f"[ACTION] Tap back berhasil di {TAP_BACK}")
            sys.stdout.flush()
        except Exception as e:
            if not simple_log:
                print(f"[ERROR] Gagal melakukan tap: {str(e)}")
            sys.stdout.flush()
        print(f"{Fore.GREEN}{user_id} | Akun polos{Style.RESET_ALL}")
        sys.stdout.flush()
        return finalize_check(user_id, driver, simple_log, running, "Akun polos", return_status)
    
    if detected_family:
        try:
            driver.click(*TAP_TENTUKAN)
            if not simple_log:
                print(f"[ACTION] Tap Tentukan berhasil di {TAP_TENTUKAN}")
            sys.stdout.flush()
        except Exception as e:
            if not simple_log:
                print(f"[ERROR] Gagal melakukan tap: {str(e)}")
            sys.stdout.flush()
        print(f"{Fore.YELLOW}{user_id} | Akun family{Style.RESET_ALL}")
        sys.stdout.flush()
        return finalize_check(user_id, driver, simple_log, running, "Akun family", return_status)
    
    if detected_belum_sandi:
        try:
            driver.click(*TAP_BACK)
            if not simple_log:
                print(f"[ACTION] Tap back berhasil di {TAP_BACK}")
            sys.stdout.flush()
        except Exception as e:
            if not simple_log:
                print(f"[ERROR] Gagal melakukan tap: {str(e)}")
            sys.stdout.flush()
        print(f"{Fore.YELLOW}{user_id} | Belum atur sandi{Style.RESET_ALL}")
        sys.stdout.flush()
        return finalize_check(user_id, driver, simple_log, running, "Belum atur sandi", return_status)
    
    if detected_tidak_ada:
        try:
            driver.click(*TAP_TENTUKAN)
            if not simple_log:
                print(f"[ACTION] Tap Tentukan berhasil di {TAP_TENTUKAN}")
            sys.stdout.flush()
        except Exception as e:
            if not simple_log:
                print(f"[ERROR] Gagal melakukan tap: {str(e)}")
            sys.stdout.flush()
        print(f"{Fore.RED}{user_id} | Akun tidak ada{Style.RESET_ALL}")
        sys.stdout.flush()
        return finalize_check(user_id, driver, simple_log, running, "Akun tidak ada", return_status)
    
    if detected_perbarui:
        try:
            driver.click(*TAP_BACK)
            if not simple_log:
                print(f"[ACTION] Tap back berhasil di {TAP_BACK}")
            sys.stdout.flush()
        except Exception as e:
            if not simple_log:
                print(f"[ERROR] Gagal melakukan tap: {str(e)}")
            sys.stdout.flush()
        print(f"{Fore.YELLOW}{user_id} | Perbarui versi{Style.RESET_ALL}")
        sys.stdout.flush()
        return finalize_check(user_id, driver, simple_log, running, "Perbarui versi", return_status)
    
    if detected_error:
        try:
            driver.click(*TAP_TENTUKAN)
            time.sleep(0.3)
            if not simple_log:
                print(f"[ACTION] Tap Tentukan berhasil")
            sys.stdout.flush()
        except Exception as e:
            if not simple_log:
                print(f"[ERROR] Gagal melakukan tap: {str(e)}")
            sys.stdout.flush()
        print(f"{Fore.RED}{user_id} | Sistem error{Style.RESET_ALL}")
        sys.stdout.flush()
        return finalize_check(user_id, driver, simple_log, running, "Sistem error", return_status)
    
    if detected_verif:
        if not simple_log:
            print(f"[ACTION] Keyword 'verifikasi google' terdeteksi! Melakukan tap close...")
        try:
            driver.click(*TAP_CLOSE_VERIF)
            if not simple_log:
                print(f"[ACTION] Tap close verifikasi berhasil di {TAP_CLOSE_VERIF}")
            sys.stdout.flush()
        except Exception as e:
            if not simple_log:
                print(f"[ERROR] Gagal melakukan tap: {str(e)}")
            sys.stdout.flush()
        print(f"{Fore.RED}{user_id} | Akun verifikasi{Style.RESET_ALL}")
        sys.stdout.flush()
        return finalize_check(user_id, driver, simple_log, running, "Akun verifikasi", return_status)
    if return_status:
        return None
    return False

def check_account(user_id, driver, areas, simple_log, max_attempts=50):
    running = [True]
    status = None
    
    try:
        try:
            driver.click(*TAP_INPUT_ID)
            time.sleep(0.3)
        except Exception as e:
            raise Exception(f"Failed to tap input ID: {str(e)}")
        
        try:
            focused = driver(focused=True)
            is_edit = focused.exists and ("EditText" in focused.info.get("className", "") or "TextInput" in focused.info.get("className", "") or focused.info.get("editable") is True)
        except Exception as e:
            raise Exception(f"Failed to check EditText: {str(e)}")
        
        if is_edit:
            for _ in range(10):
                try:
                    focused.set_text("")
                    focused.set_text(user_id)
                    try:
                        if (focused.get_text() or "") == user_id:
                            driver.click(*TAP_LUPA)
                            break
                    except Exception:
                        pass
                    time.sleep(0.1)
                except Exception as e:
                    if not simple_log:
                        print(f"[WARNING] Failed to set text: {str(e)}")
                    break
        
        for attempt in range(max_attempts):
            if not running[0]:
                break
            
            try:
                xml_text = dump_xml_text(driver)
                result = check_keywords(xml_text, user_id, driver, simple_log, running, return_status=True)
                if isinstance(result, str):
                    status = result
                    break
            except Exception as e:
                if not simple_log:
                    print(f"[WARNING] XML dump failed: {str(e)}")
            
            for area in areas:
                try:
                    ocr_text = ocr_area(driver, area)
                    result = check_keywords(ocr_text, user_id, driver, simple_log, running, return_status=True)
                    if isinstance(result, str):
                        status = result
                        break
                except Exception as e:
                    if not simple_log:
                        print(f"[WARNING] OCR failed: {str(e)}")
            if status:
                break
            time.sleep(0.2)
    except Exception as e:
        error_msg = str(e)
        if not simple_log:
            print(f"[ERROR] Error checking account for {user_id}: {error_msg}")
        else:
            print(f"[ERROR] {user_id}: {error_msg}")
        status = f"Error: {error_msg[:50]}"
    
    return status or "Tidak terdeteksi"

def ocr_loop(driver, areas, running, user_id, simple_log):
    if not simple_log:
        print("[OCR] OCR aktif, membaca area secara kontinyu...")
        print("[XML] XML dump aktif, membaca TextView secara kontinyu...")
        print("[OCR] Tekan Ctrl+C untuk menghentikan program\n")
    while running[0]:
        try:
            xml_text = dump_xml_text(driver)
            if not simple_log:
                print(f"[XML] Text: {xml_text[:100]}...")
            sys.stdout.flush()
            if check_keywords(xml_text, user_id, driver, simple_log, running):
                break
            
            for area_idx, area in enumerate(areas):
                ocr_text = ocr_area(driver, area)
                if not simple_log:
                    print(f"[OCR] Area {area_idx + 1}: {ocr_text}")
                sys.stdout.flush()
                if check_keywords(ocr_text, user_id, driver, simple_log, running):
                    break
            time.sleep(0.1)
        except KeyboardInterrupt:
            running[0] = False
            break
        except Exception as e:
            if not simple_log:
                print(f"[OCR] Error: {str(e)}")
            time.sleep(0.5)

def get_all_devices():
    devices = []
    output = run(["adb", "devices"])
    for line in output.splitlines()[1:]:
        if "\tdevice" in line:
            device_id = line.split("\t")[0]
            devices.append(device_id)
    return devices

all_devices = get_all_devices()
if not all_devices:
    sys.exit("Tidak ada device aktif.")

print(f"[INIT] Found {len(all_devices)} device(s): {all_devices}")

device_pool = []
device_locks = {}
device_pool_lock = threading.Lock()

def connect_device(device_id):
    try:
        run(["adb", "connect", device_id])
        driver = u2.connect(device_id)
        device_info = {
            "id": device_id,
            "driver": driver,
            "busy": False,
            "lock": threading.Lock()
        }
        with device_pool_lock:
            device_pool.append(device_info)
            device_locks[device_id] = threading.Lock()
        print(f"[DEVICE] Connected to device: {device_id}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to connect to {device_id}: {str(e)}")
        return False

for device_id in all_devices:
    connect_device(device_id)

if not device_pool:
    sys.exit("Gagal connect ke semua device.")

def monitor_devices():
    while True:
        try:
            time.sleep(3)
            current_devices = get_all_devices()
            current_device_ids = set(current_devices)
            
            with device_pool_lock:
                pool_device_ids = {device["id"] for device in device_pool}
                
                for device_id in current_device_ids:
                    if device_id not in pool_device_ids:
                        print(f"[DEVICE] New device detected: {device_id}")
                        connect_device(device_id)
                        with device_available:
                            device_available.notify_all()
                
                for device in device_pool[:]:
                    if device["id"] not in current_device_ids:
                        if not device["busy"]:
                            print(f"[DEVICE] Device removed/disconnected: {device['id']}")
                            try:
                                device["driver"].app_stop_all()
                            except:
                                pass
                            device_pool.remove(device)
                            if device["id"] in device_locks:
                                del device_locks[device["id"]]
                            with device_available:
                                device_available.notify_all()
                        else:
                            print(f"[DEVICE] Device {device['id']} disconnected but still in use, will remove after completion")
        except Exception as e:
            if not SIMPLE_LOG:
                print(f"[ERROR] Device monitoring error: {str(e)}")
            time.sleep(5)

monitor_thread = threading.Thread(target=monitor_devices, daemon=True)
monitor_thread.start()
print("[INIT] Device monitoring started")

ocr_areas = [OCR_AREA, OCR_AREA_2]

proses_dir = Path("proses")
proses_dir.mkdir(exist_ok=True)

processing_lock = threading.Lock()
request_queue = queue.Queue()
device_available = threading.Condition(threading.Lock())

def get_available_device():
    with device_available:
        while True:
            with device_pool_lock:
                for device in device_pool:
                    if not device["busy"]:
                        return device
            device_available.wait()

app = Flask(__name__)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

@app.route('/', methods=['GET'])
def root():
    return jsonify({
        "message": "API is running",
        "endpoint": "/checkPolos?userId={userid}"
    })

def process_request(user_id):
    device = None
    temp_file = proses_dir / f"{user_id}.tmp"
    
    try:
        temp_file.write_text(user_id)
        print(f"[API] Created temp file: {temp_file}")
        
        device = get_available_device()
        with device_pool_lock:
            if device not in device_pool:
                raise Exception("Device no longer available")
        with device["lock"]:
            if not device["busy"]:
                device["busy"] = True
                print(f"[API] Assigning userId {user_id} to device {device['id']} (Queue: {request_queue.qsize()} pending, Total devices: {len(device_pool)})")
        
        try:
            status = check_account(user_id, device["driver"], ocr_areas, SIMPLE_LOG)
            result = {
                "userId": user_id,
                "status": status
            }
        finally:
            with device_available:
                device["busy"] = False
                current_devices = get_all_devices()
                if device["id"] not in current_devices:
                    print(f"[API] Device {device['id']} no longer in ADB devices, removing from pool")
                    with device_pool_lock:
                        if device in device_pool:
                            device_pool.remove(device)
                        if device["id"] in device_locks:
                            del device_locks[device["id"]]
                else:
                    print(f"[API] Device {device['id']} is now available")
                device_available.notify()
        
        if temp_file.exists():
            temp_file.unlink()
            print(f"[API] Removed temp file: {temp_file}")
        
        return result
    except Exception as e:
        error_msg = str(e)
        if device:
            with device_available:
                device["busy"] = False
                print(f"[API] Device {device['id']} is now available (after error: {error_msg[:50]})")
                device_available.notify()
        if temp_file.exists():
            temp_file.unlink()
        if not simple_log:
            print(f"[API] Error for userId {user_id}: {error_msg}")
        result = {
            "userId": user_id,
            "status": f"Error: {error_msg[:100]}"
        }
        return result

@app.route('/checkPolos', methods=['GET'])
def check_polos():
    user_id = request.args.get('userId')
    if not user_id:
        return jsonify({"error": "userId parameter is required"}), 400
    
    print(f"\n[API] Request received for userId: {user_id}")
    
    request_queue.put(user_id)
    queue_position = request_queue.qsize()
    available_devices = sum(1 for d in device_pool if not d['busy'])
    print(f"[API] Added userId {user_id} to queue (position: {queue_position}, available devices: {available_devices}/{len(device_pool)})")
    
    try:
        result = process_request(user_id)
        if not request_queue.empty():
            request_queue.get()
        print(f"[API] Response: {result}")
        return jsonify(result)
    except Exception as e:
        if not request_queue.empty():
            request_queue.get()
        result = {
            "userId": user_id,
            "status": f"Error: {str(e)}"
        }
        print(f"[API] Error: {result}")
        return jsonify(result), 500

if __name__ == '__main__':
    print("Flask server starting on http://127.0.0.1:5000")
    print("API endpoint: http://127.0.0.1:5000/checkPolos?userId={userid}")
    print("Server ready. Waiting for manual requests...")
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)
