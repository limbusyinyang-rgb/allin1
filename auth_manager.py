import os
import sys
import json
import uuid
import hashlib
import platform
import subprocess
import urllib.request
import urllib.error
from datetime import datetime, timedelta

# =========================================================================
# THIẾT LẬP DATABASE (Thay bằng link Firebase Realtime Database của bạn)
# =========================================================================
FIREBASE_URL = "https://tooo-license-default-rtdb.asia-southeast1.firebasedatabase.app"
# =========================================================================

def get_machine_id():
    """Tạo mã định danh duy nhất cho máy tính (Hardware ID)"""
    system_info = platform.node() + platform.system() + platform.machine()
    mac = ':'.join(['{:02x}'.format((uuid.getnode() >> ele) & 0xff) for ele in range(0,8*6,8)][::-1])
    
    # Thử lấy UUID của Windows (Mạnh hơn MAC address)
    win_uuid = ""
    if platform.system() == "Windows":
        try:
            output = subprocess.check_output('wmic csproduct get uuid').decode('utf-8').split('\n')[1].strip()
            if output: win_uuid = output
        except:
            pass
            
    raw_id = f"{mac}-{win_uuid}-{system_info}"
    # Băm ra mã SHA256 cho gọn và bảo mật
    return hashlib.sha256(raw_id.encode('utf-8')).hexdigest()[:20].upper()

def check_license():
    """
    Kiểm tra bản quyền trên Firebase.
    Trả về: (is_valid, message, expiration_date_str)
    """
    if "YOUR-FIREBASE" in FIREBASE_URL:
        # Nếu chưa cấu hình Firebase, tự động cho phép qua (Bypass để bạn test)
        return True, "Chưa cấu hình Firebase - Tự động mở khóa", "Vĩnh viễn"
        
    machine_id = get_machine_id()
    url = f"{FIREBASE_URL}/machines/{machine_id}.json"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            
        if not data:
            return False, "Thiết bị chưa được đăng ký.", ""
            
        license_type = data.get("type", "")
        if license_type == "lifetime":
            return True, "Bản quyền vĩnh viễn.", "Vĩnh viễn"
            
        elif license_type == "subscription":
            exp_date_str = data.get("expiration_date")
            if not exp_date_str:
                return False, "Dữ liệu bản quyền bị lỗi.", ""
                
            exp_date = datetime.strptime(exp_date_str, "%Y-%m-%d")
            if datetime.now() <= exp_date:
                days_left = (exp_date - datetime.now()).days
                return True, f"Còn {days_left} ngày.", exp_date_str
            else:
                return False, "Bản quyền đã hết hạn.", exp_date_str
                
        return False, "Loại bản quyền không hợp lệ.", ""
        
    except Exception as e:
        return False, f"Không thể kết nối đến máy chủ: {e}", ""

def activate_license(key):
    """
    Kích hoạt mã và gắn vào máy.
    Trả về: (success, message)
    """
    if "YOUR-FIREBASE" in FIREBASE_URL:
        return False, "Vui lòng cấu hình FIREBASE_URL trong auth_manager.py trước!"
        
    key = key.strip().upper()
    if not key:
        return False, "Mã không được để trống."
        
    url = f"{FIREBASE_URL}/keys/{key}.json"
    machine_id = get_machine_id()
    
    try:
        # Lấy thông tin key
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            key_data = json.loads(response.read().decode('utf-8'))
            
        if not key_data:
            return False, "Mã không tồn tại hoặc không hợp lệ."
            
        used_by = key_data.get("used_by")
        if used_by and used_by != machine_id:
            return False, "Mã này đã được sử dụng cho một máy tính khác!"
            
        key_type = key_data.get("type") # 'lifetime' or 'subscription'
        
        # Cập nhật thông tin cho máy tính
        machine_url = f"{FIREBASE_URL}/machines/{machine_id}.json"
        
        if key_type == "lifetime":
            machine_data = {
                "type": "lifetime",
                "activated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        else: # subscription (30 days)
            # Nếu đang có subscription, cộng dồn
            current_exp = datetime.now()
            # Thử lấy hạn cũ
            req_mach = urllib.request.Request(machine_url, headers={'User-Agent': 'Mozilla/5.0'})
            try:
                with urllib.request.urlopen(req_mach, timeout=3) as resp_mach:
                    old_mach = json.loads(resp_mach.read().decode('utf-8'))
                    if old_mach and old_mach.get("type") == "subscription":
                        old_exp = datetime.strptime(old_mach.get("expiration_date"), "%Y-%m-%d")
                        if old_exp > current_exp:
                            current_exp = old_exp
            except: pass
            
            new_exp = current_exp + timedelta(days=30)
            machine_data = {
                "type": "subscription",
                "expiration_date": new_exp.strftime("%Y-%m-%d"),
                "activated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
        # Ghi vào máy
        req_put = urllib.request.Request(machine_url, data=json.dumps(machine_data).encode('utf-8'), method='PUT')
        req_put.add_header('Content-Type', 'application/json')
        with urllib.request.urlopen(req_put):
            pass
            
        # Đánh dấu key đã sử dụng (chỉ ghi nhận cho subscription, lifetime thì vẫn báo đã dùng)
        key_data["used_by"] = machine_id
        key_data["used_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        req_key_put = urllib.request.Request(url, data=json.dumps(key_data).encode('utf-8'), method='PUT')
        req_key_put.add_header('Content-Type', 'application/json')
        with urllib.request.urlopen(req_key_put):
            pass
            
        return True, "Kích hoạt thành công!"
        
    except Exception as e:
        return False, f"Lỗi kết nối: {e}"
