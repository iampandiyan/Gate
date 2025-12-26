from PyQt6.QtWidgets import QDialog, QLabel, QLineEdit, QPushButton, QVBoxLayout, QMessageBox, QFormLayout, QHBoxLayout
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import Qt
import cv2
import numpy as np
from database_manager import get_resident_by_plate, add_new_resident, log_audit, log_entry_event

class EntryDialog(QDialog):
    def __init__(self, plate_text, plate_image, current_user):
        super().__init__()
        self.plate_text = plate_text if plate_text else ""
        self.original_ocr = plate_text if plate_text else "" # Empty means Manual Mode
        self.plate_image = plate_image
        self.current_user = current_user
        
        self.setWindowTitle("Vehicle Entry Manager")
        self.setGeometry(400, 200, 500, 500)
        self.setStyleSheet("background-color: #2b2b2b; color: white;")

        self.layout = QVBoxLayout()
        
        # 1. Show Plate Image (Only if available)
        self.lbl_img = QLabel()
        self.lbl_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_img.setFixedHeight(150)
        self.lbl_img.setStyleSheet("background-color: #000; border: 1px solid #555;")
        
        if self.plate_image is not None:
            self.display_image(plate_image)
        else:
            self.lbl_img.setText("No Image (Manual Entry)")
            
        self.layout.addWidget(self.lbl_img)

        # 2. Status Label
        self.lbl_status = QLabel("Checking Database...")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        self.layout.addWidget(self.lbl_status)

        # 3. Form Fields
        form_layout = QFormLayout()
        
        self.txt_plate = QLineEdit(self.plate_text)
        self.txt_plate.setPlaceholderText("Enter Vehicle Number")
        self.txt_plate.setStyleSheet("font-size: 20px; font-weight: bold; padding: 5px; color: yellow; background-color: #444;")
        # Trigger DB check when user types manually
        self.txt_plate.editingFinished.connect(self.check_database_manual) 
        
        self.txt_name = QLineEdit()
        self.txt_flat = QLineEdit()
        self.txt_phone = QLineEdit()
        
        form_layout.addRow("License Plate:", self.txt_plate)
        form_layout.addRow("Owner Name:", self.txt_name)
        form_layout.addRow("Flat Number:", self.txt_flat)
        form_layout.addRow("Phone:", self.txt_phone)
        
        self.layout.addLayout(form_layout)

        # 4. Action Buttons
        btn_layout = QHBoxLayout()
        self.btn_allow = QPushButton("✅ APPROVE ENTRY")
        self.btn_allow.setStyleSheet("background-color: green; padding: 15px; font-weight: bold;")
        self.btn_allow.clicked.connect(self.approve_entry)
        
        self.btn_cancel = QPushButton("❌ CANCEL")
        self.btn_cancel.setStyleSheet("background-color: #555; padding: 15px; font-weight: bold;")
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.btn_allow)
        btn_layout.addWidget(self.btn_cancel)
        self.layout.addLayout(btn_layout)

        self.setLayout(self.layout)
        
        # 5. Initial Check
        self.check_database()

    def display_image(self, img_array):
        # Convert CV2 image to Qt
        rgb = cv2.cvtColor(img_array, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        self.lbl_img.setPixmap(QPixmap.fromImage(qimg).scaled(300, 150, Qt.AspectRatioMode.KeepAspectRatio))

    def check_database_manual(self):
        # Called when user manually types a number and hits enter
        self.plate_text = self.txt_plate.text().upper()
        self.check_database()

    def check_database(self):
        current_plate = self.txt_plate.text().upper()
        if not current_plate:
            self.lbl_status.setText("✍ Enter Details")
            self.lbl_status.setStyleSheet("color: white;")
            self.is_new_entry = True
            return

        resident = get_resident_by_plate(current_plate)
        
        if resident:
            # KNOWN VEHICLE
            self.lbl_status.setText("✅ RESIDENT FOUND")
            self.lbl_status.setStyleSheet("color: #00ff00; font-size: 18px; font-weight: bold;")
            
            # Pre-fill details
            self.txt_name.setText(resident[0])
            self.txt_flat.setText(resident[1])
            self.txt_phone.setText(resident[2])
            
            # Optional: Lock fields if found (or allow edit if you prefer)
            # self.txt_name.setReadOnly(True) 
            self.is_new_entry = False
        else:
            # UNKNOWN VEHICLE
            self.lbl_status.setText("⚠️ UNKNOWN / VISITOR")
            self.lbl_status.setStyleSheet("color: #ffaa00; font-size: 18px; font-weight: bold;")
            self.txt_name.clear()
            self.txt_flat.clear()
            self.txt_phone.clear()
            self.is_new_entry = True

    def approve_entry(self):
        final_plate = self.txt_plate.text().upper()
        name = self.txt_name.text()
        flat = self.txt_flat.text()
        phone = self.txt_phone.text()
        
        if not final_plate:
            QMessageBox.warning(self, "Error", "License Plate is required.")
            return

        # AUDIT LOGIC
        if not self.original_ocr:
            # Case 1: Pure Manual Entry (Button Click)
            log_audit(self.current_user, "MANUAL_ENTRY_CREATED", f"Manually allowed {final_plate}")
        elif final_plate != self.original_ocr:
            # Case 2: Correction (OCR said 'A', User changed to 'B')
            log_audit(self.current_user, "MANUAL_CORRECTION", 
                      f"OCR read '{self.original_ocr}', User changed to '{final_plate}'")
        else:
            # Case 3: Standard Approval
            pass

        # Logic for New Residents
        if self.is_new_entry:
            # If name/flat provided, save as resident. If empty, treat as visitor.
            if name and flat:
                add_new_resident(final_plate, name, flat, phone)
                log_audit(self.current_user, "ADD_RESIDENT", f"Added new vehicle {final_plate} for Flat {flat}")

        # Log Entry Event
        # If no camera image, use a black placeholder path or "Manual" string
        img_path = "MANUAL"
        if self.plate_image is not None:
            img_path = f"logs_images/{final_plate}.jpg"
            cv2.imwrite(img_path, self.plate_image)
        
        log_entry_event(final_plate, "Gate A", img_path)
        
        self.accept()
