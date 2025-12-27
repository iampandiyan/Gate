from PyQt6.QtWidgets import QDialog, QLabel, QLineEdit, QPushButton, QVBoxLayout, QMessageBox, QFormLayout, QHBoxLayout
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import Qt
import cv2
import numpy as np
from database_manager import get_resident_by_plate, add_new_resident, log_audit, log_entry_event
import os
from datetime import datetime
import logging
logger = logging.getLogger(__name__)

class EntryDialog(QDialog):
    def __init__(self, plate_text, plate_image, current_user,recapture_callback=None, gate_name="Unknown Gate"):
        super().__init__()
        self.gate_name = gate_name
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

        self.recapture_callback = recapture_callback

        # 4. Action Buttons
        btn_layout = QHBoxLayout()
        # 1. Recapture Button (NEW)
        if self.recapture_callback:
            self.btn_recapture = QPushButton("📷 RECAPTURE")
            self.btn_recapture.setStyleSheet("background-color: #0078d7; padding: 15px; font-weight: bold;")
            self.btn_recapture.clicked.connect(self.do_recapture)
            btn_layout.addWidget(self.btn_recapture)

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

        # --- 1. AUDIT TRAIL LOGIC ---
        if not self.original_ocr:
            log_audit(self.current_user, "MANUAL_ENTRY_CREATED", f"Manually allowed {final_plate}")
        elif final_plate != self.original_ocr:
            log_audit(self.current_user, "MANUAL_CORRECTION", 
                      f"OCR read '{self.original_ocr}', User changed to '{final_plate}'")

        # --- 2. ADD NEW RESIDENT LOGIC ---
        if self.is_new_entry and name and flat:
            add_new_resident(final_plate, name, flat, phone)
            log_audit(self.current_user, "ADD_RESIDENT", f"Added new vehicle {final_plate} for Flat {flat}")

        # --- 3. SAVE IMAGE WITH TIMESTAMP ---
        img_path = "MANUAL_ENTRY" # Default if no image
        
        if self.plate_image is not None:
            # A. Create folder if missing
            save_folder = "logs_images"
            if not os.path.exists(save_folder):
                os.makedirs(save_folder)
            
            # B. Create Timestamped Filename
            # Format: PLATENUMBER_YYYYMMDD_HHMMSS.jpg
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{final_plate}_{timestamp_str}.jpg"
            
            # C. Full Path
            full_path = os.path.join(save_folder, filename)
            
            # D. Save
            try:
                # Convert RGB (Qt view) back to BGR (OpenCV standard) for saving if needed, 
                # but usually self.plate_image is already BGR from the Detection Engine.
                cv2.imwrite(full_path, self.plate_image)
                img_path = full_path # Update path to save in DB
                
                logger.info("Image saved: %s", full_path)
            except Exception as e:
                logger.exception("Failed to save image %s", e)

        # --- 4. LOG ENTRY TO DATABASE ---
        log_entry_event(final_plate, self.gate_name, img_path)
        
        self.accept()

    def do_recapture(self):
        """Calls the main window to get a fresh frame"""
        if self.recapture_callback:
            logger.info("Requesting fresh frame (recapture)")
            # Call the function provided by Main Window
            new_frame, new_text = self.recapture_callback()
            
            if new_frame is not None:
                # Update Image Display
                self.plate_image = new_frame
                self.display_image(new_frame)
                
                # Update Text (if OCR found something new, else keep old or manual edit)
                if new_text:
                    self.txt_plate.setText(new_text)
                    self.plate_text = new_text
                    self.check_database() # Re-check DB with new number
                    logger.info("Recaptured OCR text: %s", new_text)
                else:                    
                    logger.warning("Recaptured image but no OCR text found")
            else:
                QMessageBox.warning(self, "Error", "Could not capture frame from camera.")

