import sys
import cv2
from PyQt6.QtWidgets import (QApplication, QMainWindow, QLabel, QVBoxLayout, 
                             QHBoxLayout, QWidget, QPushButton, QFrame, 
                             QStackedWidget, QListWidget, QSpacerItem, QSizePolicy, QMessageBox)
from PyQt6.QtGui import QImage, QPixmap, QFont, QIcon, QAction
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QSize

# Import our custom modules
from database_manager import init_db
from login_ui import LoginWindow
from change_pass_ui import ChangePasswordDialog
from detection_engine import AIEngine
from entry_dialog import EntryDialog
import time

# --- WORKER THREAD (Handles Camera) ---
class VideoThread(QThread):
    change_pixmap_signal = pyqtSignal(QImage)
    plate_detected_signal = pyqtSignal(str, object) # Sends Text and Image
    running = True

    def run(self):
        # Initialize AI Engine (Takes a few seconds to load)
        self.ai = AIEngine() 
        
        cap = cv2.VideoCapture(0)
        
        last_detection_time = 0
        cooldown_seconds = 5 # Wait 5 seconds before detecting same car again

        while self.running:
            ret, frame = cap.read()
            if ret:
                # 1. AI DETECTION LOGIC
                # Only run AI if cooldown passed
                if time.time() - last_detection_time > cooldown_seconds:
                    
                    # Run Detection
                    text, conf, crop_img = self.ai.detect_and_read(frame)
                    
                    if text:
                        print(f"🚘 Detected: {text}")
                        last_detection_time = time.time()
                        # Emit Signal to Main Thread to show Popup
                        self.plate_detected_signal.emit(text, crop_img)

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
        self.thread = VideoThread()
        self.thread.change_pixmap_signal.connect(self.update_image)
        self.thread.plate_detected_signal.connect(self.handle_detection)
        self.thread.start()

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

        # Navigation Buttons
        self.btn_home = SidebarButton("  📷  Live Monitor")
        self.btn_home.setChecked(True)
        self.btn_home.clicked.connect(lambda: self.pages.setCurrentIndex(0))
        
        self.btn_logs = SidebarButton("  📋  Entry Logs")
        self.btn_logs.clicked.connect(lambda: self.pages.setCurrentIndex(1))
        
        self.btn_settings = SidebarButton("  ⚙  Settings")
        self.btn_settings.clicked.connect(lambda: self.pages.setCurrentIndex(2))

        layout.addWidget(self.btn_home)
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
        layout = QHBoxLayout() # Split Video vs Info
        
        # LEFT: Video Feed
        video_container = QWidget()
        v_layout = QVBoxLayout()
        
        lbl_head = QLabel("Live Camera Feed")
        lbl_head.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")
        v_layout.addWidget(lbl_head)
        
        self.lbl_video = QLabel()
        self.lbl_video.setStyleSheet("background-color: black; border-radius: 8px;")
        self.lbl_video.setMinimumSize(640, 480)
        self.lbl_video.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v_layout.addWidget(self.lbl_video)
        
        video_container.setLayout(v_layout)
        
        # RIGHT: Quick Info
        info_container = QFrame()
        info_container.setFixedWidth(350)
        info_container.setStyleSheet("background-color: #252525; border-left: 1px solid #333;")
        i_layout = QVBoxLayout()
        
        lbl_last = QLabel("Last Detected Vehicle")
        lbl_last.setStyleSheet("color: #aaa; font-size: 12px;")
        
        self.lbl_plate = QLabel("---")
        self.lbl_plate.setFont(QFont("Consolas", 36, QFont.Weight.Bold))
        self.lbl_plate.setStyleSheet("color: #00ff00; margin-bottom: 20px;")
        self.lbl_plate.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        btn_manual = QPushButton("Manual Entry")
        btn_manual.setStyleSheet("background-color: #0078d7; color: white; padding: 12px; font-weight: bold; border-radius: 4px;")
        
        i_layout.addWidget(lbl_last)
        i_layout.addWidget(self.lbl_plate)
        i_layout.addWidget(btn_manual)
        i_layout.addStretch()
        
        info_container.setLayout(i_layout)

        layout.addWidget(video_container)
        layout.addWidget(info_container)
        page.setLayout(layout)
        return page

    def create_logs_page(self):
        page = QWidget()
        layout = QVBoxLayout()
        
        lbl = QLabel("Vehicle Entry History")
        lbl.setStyleSheet("color: white; font-size: 20px; margin-bottom: 10px;")
        
        # Placeholder List
        list_logs = QListWidget()
        list_logs.setStyleSheet("background-color: #252525; color: white; border: none; border-radius: 5px;")
        for i in range(10):
            list_logs.addItem(f"2023-10-27 10:0{i}:00  -  TN 0{i} AB 1234  -  Gate A")
            
        layout.addWidget(lbl)
        layout.addWidget(list_logs)
        page.setLayout(layout)
        return page

    def create_settings_page(self):
        page = QWidget()
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        lbl = QLabel("System Settings")
        lbl.setStyleSheet("color: white; font-size: 20px; margin-bottom: 20px;")
        layout.addWidget(lbl)
        
        # Change Password Button
        btn_pass = QPushButton("Change My Password")
        btn_pass.setFixedSize(200, 50)
        btn_pass.setStyleSheet("background-color: #444; color: white; border-radius: 5px;")
        btn_pass.clicked.connect(self.open_password_dialog)
        
        layout.addWidget(btn_pass)
        page.setLayout(layout)
        return page

    def update_image(self, qt_img):
        # Only update if we are on the Home Page to save resources
        if self.pages.currentIndex() == 0:
            self.lbl_video.setPixmap(QPixmap.fromImage(qt_img))

    def open_password_dialog(self):
        dialog = ChangePasswordDialog(self.username)
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
