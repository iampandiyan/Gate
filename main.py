import sys
import os
import cv2
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QVBoxLayout, QHBoxLayout, 
    QWidget, QPushButton, QFrame, QStackedWidget, QListWidget, 
    QSpacerItem, QSizePolicy, QMessageBox, QLineEdit, QDateEdit, 
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QFormLayout
)
from PyQt6.QtGui import QImage, QPixmap, QFont, QIcon, QAction
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QSize, QDate

# Import our custom modules
from database_manager import init_db, search_entry_logs, get_all_gates
from login_ui import LoginWindow
from change_pass_ui import ChangePasswordDialog
from detection_engine import AIEngine
from entry_dialog import EntryDialog
import time
from camera_setup_ui import CameraSetupDialog

# --- WORKER THREAD (Handles Camera) ---
class VideoThread(QThread):
    change_pixmap_signal = pyqtSignal(QImage)
    plate_detected_signal = pyqtSignal(str, object, str) # Sends Text and Image
    running = True
    current_frame = None

    def __init__(self, source, gate_name):
        super().__init__()
        # Check if source is digit (0,1) or string (RTSP)
        self.source = int(source) if source.isdigit() else source
        self.gate_name = gate_name
        self.ai = AIEngine() # Each camera gets its own AI instance (Heavy, but necessary for parallel)
        # Optimization: You can share one AI instance across threads if GPU VRAM is tight, 
        # using a Queue system. For now, let's keep it simple.

    def run(self):
        
        
        
        cap = cv2.VideoCapture(0)
        
        last_detection_time = 0
        cooldown_seconds = 5 # Wait 5 seconds before detecting same car again

        while self.running:
            ret, frame = cap.read()
            if ret:
                self.current_frame = frame.copy()
                # 1. AI DETECTION LOGIC
                # Only run AI if cooldown passed
                if time.time() - last_detection_time > cooldown_seconds:
                    
                    # Run Detection
                    text, conf, crop_img = self.ai.detect_and_read(frame)
                    
                    if text:
                        print(f"🚘 Detected: {text}")
                        last_detection_time = time.time()
                        # Emit Signal to Main Thread to show Popup
                        self.plate_detected_signal.emit(text, crop_img, self.gate_name)

                # 2. Update GUI Video Feed
                rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb_image.shape
                bytes_per_line = ch * w
                convert_to_qt_format = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
                p = convert_to_qt_format.scaled(800, 600, Qt.AspectRatioMode.KeepAspectRatio)
                self.change_pixmap_signal.emit(p)
            else:
                break
        cap.release()
    
    def stop(self):
        self.running = False
        self.wait()

# --- CUSTOM SIDEBAR BUTTON ---
class SidebarButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setFixedHeight(50)
        self.setFont(QFont("Segoe UI", 11))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding-left: 20px;
                border: none;
                color: #b0b0b0;
                background-color: transparent;
            }
            QPushButton:hover {
                background-color: #2d2d2d;
                color: white;
                border-left: 3px solid #555;
            }
            QPushButton:checked {
                background-color: #333;
                color: #00aaff;
                border-left: 3px solid #00aaff;
                font-weight: bold;
            }
        """)

# --- MAIN DASHBOARD WINDOW ---
class SmartGateApp(QMainWindow):
    def __init__(self, username, role):
        super().__init__()
        self.username = username
        self.role = role
        
        self.setWindowTitle("Smart Gate ANPR System")
        self.setGeometry(50, 50, 1280, 720)
        
        # Main Container
        self.central_widget = QWidget()
        self.central_widget.setStyleSheet("background-color: #121212;") 
        self.setCentralWidget(self.central_widget)
        
        self.main_layout = QHBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        self.central_widget.setLayout(self.main_layout)

        # 1. SETUP SIDEBAR
        self.setup_sidebar()
        
        # 2. SETUP PAGES AREA
        self.pages = QStackedWidget()
        self.pages.setStyleSheet("background-color: #1e1e1e;")
        self.main_layout.addWidget(self.pages)

        # 3. CREATE PAGES
        self.page_home = self.create_home_page()
        self.page_logs = self.create_logs_page()
        self.page_settings = self.create_settings_page()

        self.pages.addWidget(self.page_home)
        self.pages.addWidget(self.page_logs)
        self.pages.addWidget(self.page_settings)

        

        # Start Video
        #self.thread = VideoThread()
        #self.thread.change_pixmap_signal.connect(self.update_image)
        #self.thread.plate_detected_signal.connect(self.handle_detection)
        #self.thread.start()

        self.camera_threads = [] 
        
        # Start configured cameras
        self.start_all_cameras()

    def start_all_cameras(self):
        # 1. Clear existing
        for t in self.camera_threads:
            t.stop()
            t.wait()
        self.camera_threads.clear()

        # 2. Get from DB
        gates = get_all_gates()
        
        if not gates:
            print("No cameras configured.")
            return

        # 3. Start a thread for each
        for g_id, name, source in gates:
            thread = VideoThread(source, name)
            thread.change_pixmap_signal.connect(self.update_image) # NOTE: This logic needs update for multi-view
            thread.plate_detected_signal.connect(self.handle_detection)
            thread.start()
            self.camera_threads.append(thread)
            print(f"Started Camera: {name} on {source}")

    def handle_detection(self, text, crop_img):
        """
        Triggered when AI finds a plate.
        Pauses video (optional logic) and shows popup.
        """
        # Open the Entry Dialog
        dialog = EntryDialog(text, crop_img, self.username)
        result = dialog.exec()
        
        if result == 1:
            print("✅ Entry Approved")
            # Update the Dashboard Last Detected Label
            self.lbl_plate.setText(text)
        else:
            print("❌ Entry Rejected")

    def setup_sidebar(self):
        sidebar = QFrame()
        sidebar.setFixedWidth(250)
        sidebar.setStyleSheet("background-color: #0d0d0d; border-right: 1px solid #333;")
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # App Title / Logo Area
        lbl_title = QLabel("SMART GATE")
        lbl_title.setFixedHeight(60)
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        lbl_title.setStyleSheet("color: white; border-bottom: 1px solid #333;")
        layout.addWidget(lbl_title)

        # User Info
        lbl_user = QLabel(f"👤 {self.username.upper()}")
        lbl_user.setStyleSheet("color: #666; padding-left: 20px; font-size: 12px; margin-top: 10px; margin-bottom: 10px;")
        layout.addWidget(lbl_user)

        # --- MENU BUTTONS ---
        
        # 1. Home
        self.btn_home = SidebarButton("  📷  Live Monitor")
        self.btn_home.setChecked(True)
        self.btn_home.clicked.connect(lambda: self.pages.setCurrentIndex(0))
        
        # 2. Manual Entry (NEW BUTTON)
        self.btn_manual = SidebarButton("  ✍  Manual Entry")
        self.btn_manual.clicked.connect(self.open_manual_entry)
        
        # 3. Logs
        self.btn_logs = SidebarButton("  📋  Entry Logs")
        self.btn_logs.clicked.connect(lambda: self.pages.setCurrentIndex(1))
        
        # 4. Settings
        self.btn_settings = SidebarButton("  ⚙  Settings")
        self.btn_settings.clicked.connect(lambda: self.pages.setCurrentIndex(2))

        layout.addWidget(self.btn_home)
        layout.addWidget(self.btn_manual) # Added here
        layout.addWidget(self.btn_logs)
        layout.addWidget(self.btn_settings)
        
        # Spacer to push Logout to bottom
        layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        # Logout Button
        btn_logout = QPushButton("  🚪  Logout")
        btn_logout.setFixedHeight(50)
        btn_logout.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_logout.setStyleSheet("""
            QPushButton {
                text-align: left; padding-left: 20px; border: none; 
                color: #ff4444; background-color: transparent; font-size: 11pt;
            }
            QPushButton:hover { background-color: #2d1010; }
        """)
        btn_logout.clicked.connect(self.logout)
        layout.addWidget(btn_logout)

        sidebar.setLayout(layout)
        self.main_layout.addWidget(sidebar)

    def create_home_page(self):
        page = QWidget()
        layout = QVBoxLayout()
        
        # Header
        lbl_head = QLabel("Live Camera Feed")
        lbl_head.setStyleSheet("color: white; font-size: 18px; font-weight: bold; padding: 10px;")
        layout.addWidget(lbl_head)
        
        # Video Area (Now Full Width)
        self.lbl_video = QLabel()
        self.lbl_video.setStyleSheet("background-color: black; border-radius: 8px; border: 2px solid #333;")
        self.lbl_video.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_video.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        layout.addWidget(self.lbl_video)
        page.setLayout(layout)
        return page

    def create_logs_page(self):
        page = QWidget()
        layout = QVBoxLayout()
        
        # --- 1. FILTER BAR ---
        filter_frame = QFrame()
        filter_frame.setStyleSheet("background-color: #252525; border-radius: 5px;")
        filter_layout = QHBoxLayout()
        
        # From Date
        lbl_from = QLabel("From:")
        lbl_from.setStyleSheet("color: #aaa;")
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addDays(-7)) # Default: Last 7 days
        self.date_from.setDisplayFormat("yyyy-MM-dd")
        self.date_from.setStyleSheet("padding: 5px; color: white; background: #444;")

        # To Date
        lbl_to = QLabel("To:")
        lbl_to.setStyleSheet("color: #aaa;")
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setDisplayFormat("yyyy-MM-dd")
        self.date_to.setStyleSheet("padding: 5px; color: white; background: #444;")

        # Vehicle Number
        self.txt_filter_plate = QLineEdit()
        self.txt_filter_plate.setPlaceholderText("Vehicle No (e.g. TN01)")
        self.txt_filter_plate.setStyleSheet("padding: 5px; color: white; background: #444;")

        # Flat Number
        self.txt_filter_flat = QLineEdit()
        self.txt_filter_flat.setPlaceholderText("Flat No")
        self.txt_filter_flat.setStyleSheet("padding: 5px; color: white; background: #444;")

        # Search Button
        btn_search = QPushButton("🔍 Search")
        btn_search.setStyleSheet("background-color: #0078d7; padding: 6px 15px; font-weight: bold; border-radius: 4px;")
        btn_search.clicked.connect(self.perform_log_search)

        filter_layout.addWidget(lbl_from)
        filter_layout.addWidget(self.date_from)
        filter_layout.addWidget(lbl_to)
        filter_layout.addWidget(self.date_to)
        filter_layout.addWidget(self.txt_filter_plate)
        filter_layout.addWidget(self.txt_filter_flat)
        filter_layout.addWidget(btn_search)
        
        filter_frame.setLayout(filter_layout)
        layout.addWidget(filter_frame)

        # --- 2. RESULTS TABLE ---
        self.table_logs = QTableWidget()
        self.table_logs.setColumnCount(5)
        self.table_logs.setHorizontalHeaderLabels(["Date & Time", "Flat No", "Vehicle No", "Gate", "Image"])
        
        # Table Styling
        self.table_logs.setStyleSheet("""
            QTableWidget { background-color: #1e1e1e; gridline-color: #333; color: white; border: none; }
            QHeaderView::section { background-color: #2d2d2d; padding: 5px; border: 1px solid #333; color: #aaa; }
            QTableWidget::item { padding: 5px; }
        """)
        
        # Column Resizing
        header = self.table_logs.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch) # Date
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents) # Flat
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents) # Plate
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents) # Gate
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch) # Image path

        # Read-Only & Selection
        self.table_logs.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_logs.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_logs.setIconSize(QSize(100, 50)) # For thumbnails

        layout.addWidget(self.table_logs)
        page.setLayout(layout)
        
        # Initial Load
        self.perform_log_search() 
        
        return page

    def perform_log_search(self):
        # 1. Get Filter Values
        f_date = self.date_from.date().toString("yyyy-MM-dd")
        t_date = self.date_to.date().toString("yyyy-MM-dd")
        plate = self.txt_filter_plate.text().strip()
        flat = self.txt_filter_flat.text().strip()

        # 2. Query DB
        results = search_entry_logs(f_date, t_date, plate, flat)

        # 3. Populate Table
        self.table_logs.setRowCount(0) # Clear previous
        
        for row_idx, (entry_time, flat_no, plate_no, img_path, gate) in enumerate(results):
            self.table_logs.insertRow(row_idx)
            self.table_logs.setRowHeight(row_idx, 60) # Taller rows for images

            # Date
            self.table_logs.setItem(row_idx, 0, QTableWidgetItem(str(entry_time)))
            
            # Flat (Colorize Visitors)
            item_flat = QTableWidgetItem(str(flat_no))
            if flat_no == 'Visitor':
                item_flat.setForeground(Qt.GlobalColor.yellow)
            self.table_logs.setItem(row_idx, 1, item_flat)

            # Plate
            item_plate = QTableWidgetItem(plate_no)
            item_plate.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
            self.table_logs.setItem(row_idx, 2, item_plate)

            # Gate
            self.table_logs.setItem(row_idx, 3, QTableWidgetItem(gate))

            # Image (Thumbnail)
            item_img = QTableWidgetItem()
            if img_path and img_path != "MANUAL" and os.path.exists(img_path):
                # Load image, scale it to icon
                pixmap = QPixmap(img_path)
                if not pixmap.isNull():
                    icon = QIcon(pixmap)
                    item_img.setIcon(icon)
                    item_img.setText(" (View)") # Text helps verify row exists
            else:
                item_img.setText("No Image")
            
            self.table_logs.setItem(row_idx, 4, item_img)

        if not results:
            self.table_logs.setRowCount(1)
            self.table_logs.setItem(0, 0, QTableWidgetItem("No records found."))


    def create_settings_page(self):
        page = QWidget()
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        lbl = QLabel("System Settings")
        lbl.setStyleSheet("color: white; font-size: 20px; margin-bottom: 20px;")
        layout.addWidget(lbl)

        btn_cam_setup = QPushButton("Configure Cameras")
        btn_cam_setup.clicked.connect(self.open_camera_setup)
        layout.addWidget(btn_cam_setup)
        
        # Change Password Button
        btn_pass = QPushButton("Change My Password")
        btn_pass.setFixedSize(200, 50)
        btn_pass.setStyleSheet("background-color: #444; color: white; border-radius: 5px;")
        btn_pass.clicked.connect(self.open_password_dialog)
        
        layout.addWidget(btn_pass)
        page.setLayout(layout)
        return page
    
    def open_camera_setup(self):
        dialog = CameraSetupDialog()
        dialog.exec()
        # Restart cameras after config changes
        self.start_all_cameras()

    def update_image(self, qt_img):
        # 1. Always keep the QPixmap ready
        pixmap = QPixmap.fromImage(qt_img)
        
        # 2. Update the label ONLY. 
        # Since the widget is in a QStackedWidget, it exists but is just hidden.
        # Updating a hidden widget is cheap.
        self.lbl_video.setPixmap(pixmap)

    def open_password_dialog(self):
        dialog = ChangePasswordDialog(self.username)
        dialog.exec()

    def open_manual_entry(self):
        # Open Dialog with Empty Data for Manual Entry
        dialog = EntryDialog("", None, self.username)
        dialog.exec()
        
    def handle_detection(self, text, crop_img):
        # Triggered by AI
        dialog = EntryDialog(text, crop_img, self.username)
        dialog.exec()

    def logout(self):
        reply = QMessageBox.question(self, 'Logout', 'Are you sure you want to logout?',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.thread.stop() # Stop camera
            self.close() # Close Dashboard
            
            # Restart Login
            self.login_window = LoginWindow()
            if self.login_window.exec() == 1:
                self.new_dashboard = SmartGateApp(self.login_window.username, self.login_window.user_role)
                self.new_dashboard.show()
        # Inside SmartGateApp class

    def perform_recapture(self, target_thread):
        """
        Called by EntryDialog when user clicks 'Recapture'.
        Args: target_thread (VideoThread) - The specific camera to grab frame from
        """
        if not target_thread:
            return None, None

        # 1. Get latest frame from the specific thread
        frame = target_thread.current_frame
        if frame is None:
            return None, None
            
        # 2. Run AI manually on this frame
        # We use the AI instance belonging to that thread
        text, conf, crop_img = target_thread.ai.detect_and_read(frame)
        
        # Return the crop if found, else return the full frame as fallback
        final_img = crop_img if crop_img is not None else frame
        
        return final_img, text


    def handle_detection(self, text, crop_img, gate_name):
        print(f"🔔 Detection at {gate_name}: {text}")
        
        # 1. Find the thread that triggered this detection
        target_thread = None
        for t in self.camera_threads:
            if t.gate_name == gate_name:
                target_thread = t
                break
        
        # 2. Create a "Wrapper" function to pass to the Dialog
        # This freezes 'target_thread' into the function call
        if target_thread:
            recapture_func = lambda: self.perform_recapture(target_thread)
        else:
            recapture_func = None

        # 3. Open Dialog
        dialog = EntryDialog(text, crop_img, self.username, recapture_func, gate_name)
        dialog.exec()



    # Update open_manual_entry to pass this callback too
    def open_manual_entry(self):
        # 1. Default to the first camera if available
        target_thread = self.camera_threads[0] if self.camera_threads else None
        gate_name = target_thread.gate_name if target_thread else "Manual"

        # 2. Create Callback
        if target_thread:
             recapture_func = lambda: self.perform_recapture(target_thread)
        else:
             recapture_func = None

        # 3. Open Dialog
        dialog = EntryDialog("", None, self.username, recapture_func, gate_name)
        dialog.exec()



if __name__ == '__main__':
    init_db()
    app = QApplication(sys.argv)
    
    # Set global font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    login = LoginWindow()
    if login.exec() == 1:
        dashboard = SmartGateApp(login.username, login.user_role)
        dashboard.show()
        sys.exit(app.exec())
    else:
        sys.exit(0)
