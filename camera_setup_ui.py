import cv2
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QListWidget, QLineEdit, QMessageBox, QComboBox, 
    QGroupBox, QFormLayout
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
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
        self.setGeometry(300, 200, 850, 500) # Widen window for side-by-side layout
        
        # Professional Dark Theme Styling
        self.setStyleSheet("""
            QDialog { background-color: #2b2b2b; color: white; font-family: Segoe UI; }
            
            QGroupBox { 
                border: 1px solid #555; 
                border-radius: 6px; 
                margin-top: 20px; 
                font-weight: bold; 
                color: #ddd;
            }
            QGroupBox::title { 
                subcontrol-origin: margin; 
                left: 10px; 
                padding: 0 5px; 
            }
            
            QLabel { font-size: 13px; color: #ccc; }
            
            QLineEdit, QComboBox, QListWidget { 
                background-color: #3a3a3a; 
                border: 1px solid #555; 
                border-radius: 4px; 
                color: white; 
                padding: 6px;
                font-size: 13px;
            }
            QLineEdit:focus, QComboBox:focus { border: 1px solid #0078d7; }
            
            QPushButton { 
                padding: 8px 16px; 
                border-radius: 4px; 
                font-weight: bold; 
            }
        """)

        # Main Layout: Side-by-Side (Horizontal)
        self.main_layout = QHBoxLayout()
        self.main_layout.setSpacing(20)
        self.main_layout.setContentsMargins(20, 20, 20, 20)

        # ==========================================
        # LEFT COLUMN: EXISTING GATES LIST
        # ==========================================
        self.group_list = QGroupBox("Configured Gates")
        self.layout_list = QVBoxLayout()
        
        self.list_gates = QListWidget()
        self.list_gates.setAlternatingRowColors(True)
        self.layout_list.addWidget(self.list_gates)

        self.btn_delete = QPushButton("🗑 Remove Selected Gate")
        self.btn_delete.setStyleSheet("background-color: #d9534f; color: white;")
        self.btn_delete.clicked.connect(self.remove_gate)
        self.layout_list.addWidget(self.btn_delete)

        self.group_list.setLayout(self.layout_list)
        self.main_layout.addWidget(self.group_list, 1) # Stretch Factor 1 (50%)

        # ==========================================
        # RIGHT COLUMN: ADD / EDIT GATE
        # ==========================================
        self.group_form = QGroupBox("Add New Gate")
        self.layout_form = QVBoxLayout()
        self.layout_form.setSpacing(15)
        self.layout_form.setContentsMargins(15, 25, 15, 15)

        # 1. Scan Button (Top of Right Column)
        self.btn_scan = QPushButton("🔍 Scan for Local Cameras")
        self.btn_scan.setStyleSheet("background-color: #0275d8; color: white;")
        self.btn_scan.clicked.connect(self.start_scan)
        self.layout_form.addWidget(self.btn_scan)

        # 2. Form Fields (Aligned Labels)
        self.form_layout = QFormLayout()
        self.form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.form_layout.setVerticalSpacing(15)

        # Name Field
        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("e.g., Main Entrance")
        self.form_layout.addRow("Gate Name:", self.txt_name)

        # Source Field
        self.combo_source = QComboBox()
        self.combo_source.setEditable(True) # Allow typing RTSP
        self.combo_source.setPlaceholderText("Select USB Camera or Type RTSP URL")
        self.form_layout.addRow("Camera Source:", self.combo_source)

        self.layout_form.addLayout(self.form_layout)

        # Spacer to push Save button to bottom
        self.layout_form.addStretch()

        # 3. Save Button
        self.btn_save = QPushButton("💾 Save Configuration")
        self.btn_save.setFixedHeight(45)
        self.btn_save.setStyleSheet("background-color: #28a745; color: white; font-size: 14px;")
        self.btn_save.clicked.connect(self.save_gate)
        self.layout_form.addWidget(self.btn_save)

        self.group_form.setLayout(self.layout_form)
        self.main_layout.addWidget(self.group_form, 1) # Stretch Factor 1 (50%)

        # Set Main Layout
        self.setLayout(self.main_layout)

        # Initial Load
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
        if "Index: " in source_text:
            source = source_text.split("Index: ")[1]
        else:
            source = source_text # It's an RTSP URL

        if add_or_update_gate(name, source):
            QMessageBox.information(self, "Success", "Gate Configured!")
            self.load_gates()
            self.txt_name.clear()
            self.combo_source.setEditText("")
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
        else:
            QMessageBox.warning(self, "Selection Error", "Please select a gate to remove.")
