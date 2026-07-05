import sys
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QMessageBox, QHBoxLayout, QApplication)
from PyQt6.QtCore import Qt
import auth_manager

class LicenseDialog(QDialog):
    def __init__(self, machine_id, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Kích hoạt bản quyền")
        self.setFixedSize(450, 250)
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Dialog)
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a20;
                color: white;
            }
            QLabel {
                color: #a0aec0;
                font-size: 13px;
            }
            QLineEdit {
                background-color: #2d2d3a;
                border: 1px solid #444;
                border-radius: 4px;
                color: white;
                padding: 8px;
                font-size: 14px;
            }
            QPushButton {
                background-color: #a855f7;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #9333ea;
            }
            QPushButton#btn_copy {
                background-color: #4b5563;
                padding: 5px;
            }
            QPushButton#btn_copy:hover {
                background-color: #374151;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        title = QLabel("CẦN KÍCH HOẠT BẢN QUYỀN ĐỂ SỬ DỤNG")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #ef4444;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Machine ID Row
        hwid_layout = QHBoxLayout()
        lbl_hwid = QLabel("Mã máy của bạn:")
        self.txt_hwid = QLineEdit(machine_id)
        self.txt_hwid.setReadOnly(True)
        btn_copy = QPushButton("Copy")
        btn_copy.setObjectName("btn_copy")
        btn_copy.clicked.connect(lambda: QApplication.clipboard().setText(machine_id))
        
        hwid_layout.addWidget(lbl_hwid)
        hwid_layout.addWidget(self.txt_hwid)
        hwid_layout.addWidget(btn_copy)
        layout.addLayout(hwid_layout)
        
        layout.addWidget(QLabel("Vui lòng gửi Mã máy cho Admin để mua hoặc nhận Mã Kích Hoạt."))
        
        # Key Entry
        self.txt_key = QLineEdit()
        self.txt_key.setPlaceholderText("Nhập mã kích hoạt (XXXX-XXXX-XXXX-XXXX)...")
        layout.addWidget(self.txt_key)
        
        self.btn_activate = QPushButton("Kích Hoạt")
        self.btn_activate.clicked.connect(self.on_activate)
        layout.addWidget(self.btn_activate)
        
    def on_activate(self):
        key = self.txt_key.text().strip()
        if not key:
            QMessageBox.warning(self, "Lỗi", "Vui lòng nhập mã kích hoạt!")
            return
            
        self.btn_activate.setText("Đang kiểm tra...")
        self.btn_activate.setEnabled(False)
        QApplication.processEvents()
        
        success, msg = auth_manager.activate_license(key)
        
        self.btn_activate.setEnabled(True)
        self.btn_activate.setText("Kích Hoạt")
        
        if success:
            QMessageBox.information(self, "Thành công", msg)
            self.accept() # Close dialog and return True
        else:
            QMessageBox.critical(self, "Thất bại", msg)

def require_license():
    """Kiểm tra bản quyền, nếu không hợp lệ thì hiển thị cửa sổ nhập mã."""
    is_valid, msg, exp_date = auth_manager.check_license()
    if is_valid:
        return True, msg, exp_date
        
    # Nếu không hợp lệ, hiện hộp thoại
    machine_id = auth_manager.get_machine_id()
    dialog = LicenseDialog(machine_id)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return True, "Đã kích hoạt", ""
    return False, msg, ""
