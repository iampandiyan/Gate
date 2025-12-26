from PyQt6.QtWidgets import QDialog, QLabel, QLineEdit, QPushButton, QVBoxLayout, QMessageBox
from database_manager import check_login

class LoginWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SmartGate Login")
        self.setGeometry(450, 300, 300, 250)
        self.setStyleSheet("""
            QDialog { background-color: #2b2b2b; color: white; }
            QLabel { color: white; font-size: 14px; }
            QLineEdit { padding: 8px; border-radius: 4px; background-color: #444; color: white; }
            QPushButton { background-color: #0078d7; color: white; padding: 10px; font-weight: bold; border-radius: 4px; }
            QPushButton:hover { background-color: #005a9e; }
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        
        self.lbl_title = QLabel("🔒 Secure Access")
        self.lbl_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #00aaff; margin-bottom: 10px;")
        
        self.lbl_user = QLabel("Username:")
        self.txt_user = QLineEdit()
        
        self.lbl_pass = QLabel("Password:")
        self.txt_pass = QLineEdit()
        self.txt_pass.setEchoMode(QLineEdit.EchoMode.Password)
        
        self.btn_login = QPushButton("LOGIN")
        self.btn_login.clicked.connect(self.attempt_login)
        
        layout.addWidget(self.lbl_title)
        layout.addWidget(self.lbl_user)
        layout.addWidget(self.txt_user)
        layout.addWidget(self.lbl_pass)
        layout.addWidget(self.txt_pass)
        layout.addWidget(self.btn_login)
        layout.addStretch()
        
        self.setLayout(layout)
        
        self.user_role = None
        self.username = None

    def attempt_login(self):
        user = self.txt_user.text().strip()
        pwd = self.txt_pass.text().strip()
        
        if not user or not pwd:
            QMessageBox.warning(self, "Input Error", "Please enter both username and password.")
            return

        success, role = check_login(user, pwd)
        
        if success:
            self.user_role = role
            self.username = user
            self.accept()
        else:
            QMessageBox.critical(self, "Access Denied", "Invalid Username or Password")
