import cv2
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QListWidget, QLineEdit, QMessageBox, QComboBox)
from PyQt6.QtCore import QThread, pyqtSignal
from database_manager import add_or_update_gate, get_all_gates, delete_gate

class CameraScanner(QThread):
    found_signal = pyqtSignal(list)

    def run(self):
        available_cams = []
        # Check first 5 indices (0 to 4)
        for i in range(5):
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW) # DSHOW is faster on Windows
            if cap.isOpened():
                ret, _ = cap.read()
                if ret:
                    available_cams.append(f"USB Camera Index: {i}")
                cap.release()
        self.found_signal.emit(available_cams)

class CameraSetupDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gate & Camera Configuration")
        self.setGeometry(300, 200, 600, 500)
        self.setStyleSheet("background-color: #2b2b2b; color: white;")
        
        layout = QVBoxLayout()
        
        # 1. Existing Gates List
        layout.addWidget(QLabel("--- Configured Gates ---"))
        self.list_gates = QListWidget()
        self.list_gates.setStyleSheet("background: #444; border: 1px solid #555;")
        layout.addWidget(self.list_gates)
        
        btn_delete = QPushButton("🗑 Remove Selected Gate")
        btn_delete.setStyleSheet("background-color: #d9534f; padding: 5px;")
        btn_delete.clicked.connect(self.remove_gate)
        layout.addWidget(btn_delete)
        
        layout.addSpacing(20)
        
        # 2. Add New Gate Area
        layout.addWidget(QLabel("--- Add New Gate ---"))
        
        # Scan Button
        self.btn_scan = QPushButton("🔍 Scan for Local Cameras")
        self.btn_scan.setStyleSheet("background-color: #0275d8; padding: 8px;")
        self.btn_scan.clicked.connect(self.start_scan)
        layout.addWidget(self.btn_scan)
        
        # Dropdown for Source
        self.combo_source = QComboBox()
        self.combo_source.setStyleSheet("padding: 5px; background: #555;")
        self.combo_source.setEditable(True) # Allow typing RTSP URL
        self.combo_source.setPlaceholderText("Select Camera OR Type RTSP URL")
        layout.addWidget(self.combo_source)
        
        # Name Input
        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("Enter Gate Name (e.g., Entry Gate A)")
        self.txt_name.setStyleSheet("padding: 5px; background: #555;")
        layout.addWidget(self.txt_name)
        
        # Save Button
        btn_save = QPushButton("💾 Save Configuration")
        btn_save.setStyleSheet("background-color: #5cb85c; padding: 10px; font-weight: bold;")
        btn_save.clicked.connect(self.save_gate)
        layout.addWidget(btn_save)
        
        self.setLayout(layout)
        self.load_gates()

    def start_scan(self):
        self.btn_scan.setText("Scanning... Please Wait")
        self.btn_scan.setEnabled(False)
        self.scanner = CameraScanner()
        self.scanner.found_signal.connect(self.on_scan_complete)
        self.scanner.start()

    def on_scan_complete(self, cams):
        self.combo_source.clear()
        self.combo_source.addItems(cams)
        self.btn_scan.setText("🔍 Scan for Local Cameras")
        self.btn_scan.setEnabled(True)
        if not cams:
            QMessageBox.information(self, "Scan Result", "No USB cameras found. You can enter RTSP URL manually.")

    def save_gate(self):
        name = self.txt_name.text().strip()
        source_text = self.combo_source.currentText()
        
        if not name or not source_text:
            QMessageBox.warning(self, "Error", "Name and Source are required.")
            return
            
        # Parse Source (Extract '0' from 'USB Camera Index: 0')
        if "Index:" in source_text:
            source = source_text.split("Index: ")[1]
        else:
            source = source_text # It's an RTSP URL
            
        if add_or_update_gate(name, source):
            QMessageBox.information(self, "Success", "Gate Configured!")
            self.load_gates()
            self.txt_name.clear()
        else:
            QMessageBox.warning(self, "Error", "Failed to save. Name might be duplicate.")

    def load_gates(self):
        self.list_gates.clear()
        gates = get_all_gates()
        for g_id, name, src in gates:
            self.list_gates.addItem(f"{g_id} | {name} | Source: {src}")

    def remove_gate(self):
        row = self.list_gates.currentRow()
        if row >= 0:
            item_text = self.list_gates.item(row).text()
            gate_id = item_text.split(" | ")[0]
            delete_gate(gate_id)
            self.load_gates()
