from PyQt6.QtWidgets import QDialog, QLabel, QLineEdit, QPushButton, QVBoxLayout, QMessageBox
from database_manager import change_password

class ChangePasswordDialog(QDialog):
    def __init__(self, username):
        super().__init__()
        self.username = username
        self.setWindowTitle("Change Password")
        self.setGeometry(450, 300, 350, 300)
        self.setStyleSheet("""
            QDialog { background-color: #2b2b2b; color: white; }
            QLabel { color: white; font-size: 12px; }
            QLineEdit { padding: 8px; border-radius: 4px; background-color: #444; color: white; }
            QPushButton { background-color: #28a745; color: white; padding: 10px; font-weight: bold; border-radius: 4px; }
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(10)
        
        self.lbl_title = QLabel(f"Updating Password for: {username}")
        self.lbl_title.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 10px;")
        
        self.lbl_old = QLabel("Current Password:")
        self.txt_old = QLineEdit()
        self.txt_old.setEchoMode(QLineEdit.EchoMode.Password)
        
        self.lbl_new = QLabel("New Password:")
        self.txt_new = QLineEdit()
        self.txt_new.setEchoMode(QLineEdit.EchoMode.Password)

        self.lbl_confirm = QLabel("Confirm New Password:")
        self.txt_confirm = QLineEdit()
        self.txt_confirm.setEchoMode(QLineEdit.EchoMode.Password)
        
        self.btn_save = QPushButton("Update Password")
        self.btn_save.clicked.connect(self.save_password)
        
        layout.addWidget(self.lbl_title)
        layout.addWidget(self.lbl_old)
        layout.addWidget(self.txt_old)
        layout.addWidget(self.lbl_new)
        layout.addWidget(self.txt_new)
        layout.addWidget(self.lbl_confirm)
        layout.addWidget(self.txt_confirm)
        layout.addStretch()
        
        self.setLayout(layout)

    def save_password(self):
        old = self.txt_old.text()
        new = self.txt_new.text()
        confirm = self.txt_confirm.text()
        
        if new != confirm:
            QMessageBox.warning(self, "Error", "New Passwords do not match!")
            return
            
        if len(new) < 4:
            QMessageBox.warning(self, "Error", "Password too short! (Min 4 chars)")
            return

        success, msg = change_password(self.username, old, new)
        
        if success:
            QMessageBox.information(self, "Success", msg)
            self.accept()
        else:
            QMessageBox.warning(self, "Failed", msg)
