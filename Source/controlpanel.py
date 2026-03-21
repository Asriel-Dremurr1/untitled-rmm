# controlpanel.py
import sys, os, json, time, base64
from datetime import datetime, timezone
from functools import partial
from threading import Event

import requests
from urllib3.exceptions import InsecureRequestWarning
from PyQt5 import QtCore, QtWidgets, QtGui

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

SERVERS_FILE = "servers.json"
DEFAULT_SERVERS = []

# ---------------- Persistence ----------------
def load_servers():
    if not os.path.exists(SERVERS_FILE):
        save_servers(DEFAULT_SERVERS)
    try:
        with open(SERVERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return DEFAULT_SERVERS

def save_servers(data):
    with open(SERVERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ---------------- Helpers ----------------
def iso_to_dt(s):
    """Конвертирует ISO строку в datetime с timezone"""
    if not s: 
        return None
    try:
        # Убираем Z если есть
        if s.endswith('Z'):
            s = s[:-1] + '+00:00'
        dt = datetime.fromisoformat(s)
        # Если нет часового пояса, добавляем UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception as e:
        print(f"Ошибка парсинга времени: {s}, ошибка: {e}")
        return None

def is_online(last_seen_iso, threshold=120):
    """Проверяет онлайн статус агента по времени"""
    dt = iso_to_dt(last_seen_iso)
    if not dt: 
        return False
    now = datetime.now(timezone.utc)
    return (now - dt).total_seconds() < threshold

# ---------------- Connect Worker ----------------
class ConnectWorker(QtCore.QThread):
    progress = QtCore.pyqtSignal(str)
    finished_ok = QtCore.pyqtSignal(object)
    finished_fail = QtCore.pyqtSignal(str)

    def __init__(self, base_url, verify_ssl, tries=10, delay=3):
        super().__init__()
        self.base = base_url.rstrip("/")
        self.verify = verify_ssl
        self.tries = tries
        self.delay = delay
        self._stop = Event()

    def stop(self):
        self._stop.set()

    def run(self):
        sess = requests.Session()
        sess.verify = self.verify
        for i in range(1, self.tries+1):
            if self._stop.is_set():
                self.progress.emit("Отменено")
                self.finished_fail.emit("cancelled")
                return
            try:
                self.progress.emit(f"Попытка {i}/{self.tries} → {self.base}/server_info")
                r = sess.get(self.base + "/server_info", timeout=6)
                if r.status_code == 200:
                    self.progress.emit("Сервер доступен")
                    self.finished_ok.emit(sess)
                    return
                else:
                    self.progress.emit(f"Ответ {r.status_code}, ждём {self.delay}s")
            except Exception as e:
                self.progress.emit(f"Ошибка: {e}")
            time.sleep(self.delay)
        self.finished_fail.emit("no_response")

# ---------------- Dark Theme Stylesheet ----------------
DARK_THEME = """
/* Main window */
QMainWindow {
    background-color: #1e1e1e;
    color: #d4d4d4;
}

/* Специальные стили для кнопок в таблицах */
QTableWidget QPushButton {
    padding: 8px 12px;
    margin: 2px;
    border-radius: 4px;
    font-size: 12pt;
    min-height: 32px;
    min-width: 70px;
}

QTableWidget QPushButton:hover {
    background-color: #4a4a4a;
    transform: translateY(-1px);
}

/* Для кнопок с иконками/эмодзи */
QTableWidget QPushButton[icon-mode="true"] {
    font-size: 14pt;
    padding: 6px;
    min-width: 40px;
    max-width: 40px;
}

/* Кнопки действий в ячейках */
QTableWidget QWidget {
    background-color: transparent;
}

/* Widgets */
QWidget {
    background-color: #252525;
    color: #d4d4d4;
    font-family: 'Segoe UI', 'Arial';
    font-size: 12pt;
    border: none;
}

QTableWidget#table_users QPushButton {
    padding: 5px 8px;
    margin: 1px;
    border-radius: 4px;
    font-size: 10pt;
    min-width: 30px;
    max-width: 60px;
}

QTableWidget#table_users QLabel {
    color: #888;
    font-style: italic;
    padding: 5px;
}

QTableWidget QPushButton {
    padding: 5px 8px;
    margin: 1px;
    border-radius: 4px;
    font-size: 10pt;
    min-width: 30px;
    max-width: 100px;
}

QTableWidget QPushButton:hover {
    background-color: #4a4a4a;
}

/* Для кнопок с иконками */
QTableWidget QPushButton[icon-only="true"] {
    padding: 5px;
    min-width: 30px;
    max-width: 30px;
}

/* Labels */
QLabel {
    color: #d4d4d4;
    padding: 2px;
}

QLabel[title="true"] {
    font-size: 14pt;
    font-weight: bold;
    color: #ffffff;
    padding: 6px 0px;
}

/* Push buttons */
QPushButton {
    background-color: #3c3c3c;
    color: #d4d4d4;
    border: 1px solid #555;
    border-radius: 6px;
    padding: 8px 16px;
    margin: 2px;
    font-weight: 500;
    min-height: 28px;
    transition: all 0.2s;
}

QPushButton:hover {
    background-color: #4a4a4a;
    border-color: #666;
    transform: translateY(-1px);
}

QPushButton:pressed {
    background-color: #2c2c2c;
    transform: translateY(0px);
}

QPushButton:disabled {
    background-color: #2a2a2a;
    color: #777;
    border-color: #444;
}

/* Special buttons */
QPushButton[primary="true"] {
    background-color: #0d6efd;
    color: white;
    border-color: #0b5ed7;
    font-weight: bold;
}

QPushButton[primary="true"]:hover {
    background-color: #0b5ed7;
}

QPushButton[danger="true"] {
    background-color: #dc3545;
    color: white;
    border-color: #bb2d3b;
}

QPushButton[danger="true"]:hover {
    background-color: #bb2d3b;
}

QPushButton[success="true"] {
    background-color: #198754;
    color: white;
    border-color: #157347;
}

QPushButton[success="true"]:hover {
    background-color: #157347;
}

/* Line edits */
QLineEdit {
    background-color: #2d2d2d;
    color: #d4d4d4;
    border: 1px solid #555;
    border-radius: 4px;
    padding: 6px 8px;
    selection-background-color: #0d6efd;
}

QLineEdit:focus {
    border-color: #0d6efd;
    background-color: #333333;
}

QLineEdit:disabled {
    background-color: #2a2a2a;
    color: #777;
    border-color: #444;
}

/* Text edits */
QTextEdit, QPlainTextEdit {
    background-color: #2d2d2d;
    color: #d4d4d4;
    border: 1px solid #555;
    border-radius: 4px;
    padding: 6px;
    selection-background-color: #0d6efd;
}

QTextEdit:focus, QPlainTextEdit:focus {
    border-color: #0d6efd;
}

/* Combo boxes */
QComboBox {
    background-color: #2d2d2d;
    color: #d4d4d4;
    border: 1px solid #555;
    border-radius: 4px;
    padding: 6px 8px;
    min-height: 28px;
}

QComboBox:hover {
    border-color: #666;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox::down-arrow {
    image: url(down_arrow.png);
    width: 12px;
    height: 12px;
}

QComboBox QAbstractItemView {
    background-color: #2d2d2d;
    color: #d4d4d4;
    border: 1px solid #555;
    selection-background-color: #0d6efd;
}

/* List widgets */
QListWidget {
    background-color: #2d2d2d;
    color: #d4d4d4;
    border: 1px solid #555;
    border-radius: 4px;
    padding: 2px;
    outline: none;
}

QListWidget::item {
    padding: 6px 8px;
    border-radius: 3px;
}

QListWidget::item:hover {
    background-color: #3a3a3a;
}

QListWidget::item:selected {
    background-color: #0d6efd;
    color: white;
}

/* Table widgets */
QTableWidget {
    background-color: #2d2d2d;
    color: #d4d4d4;
    gridline-color: #444;
    border: 1px solid #555;
    border-radius: 4px;
    alternate-background-color: #282828;
    selection-background-color: #0d6efd;
    selection-color: white;
}

QHeaderView::section {
    background-color: #3c3c3c;
    color: #d4d4d4;
    padding: 10px;
    border: none;
    border-right: 1px solid #555;
    border-bottom: 1px solid #555;
    font-weight: bold;
    font-size: 11pt;
    qproperty-defaultAlignment: AlignLeft;
}

QHeaderView::section:hover {
    background-color: #4a4a4a;
    cursor: pointer;
}

QHeaderView::section:pressed {
    background-color: #2c2c2c;
}

/* Иконки сортировки в заголовках */
QHeaderView::section:sort-indicator {
    subcontrol-position: right center;
    subcontrol-origin: margin;
    width: 16px;
    height: 16px;
}

QHeaderView::section:sort-indicator:ascending {
    image: url(up_arrow.png);
}

QHeaderView::section:sort-indicator:descending {
    image: url(down_arrow.png);
}

QHeaderView::section:last {
    border-right: none;
}

QTableView QTableCornerButton::section {
    background-color: #3c3c3c;
    border: none;
}

/* Scroll areas */
QScrollArea {
    background-color: transparent;
    border: none;
}

QScrollBar:vertical, QScrollBar:horizontal {
    background-color: #2d2d2d;
    border-radius: 6px;
    width: 12px;
    height: 12px;
}

QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background-color: #555;
    border-radius: 6px;
    min-height: 20px;
    min-width: 20px;
}

QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {
    background-color: #666;
}

QScrollBar::add-line, QScrollBar::sub-line {
    height: 0px;
    width: 0px;
}

/* Tab widgets */
QTabWidget::pane {
    background-color: #252525;
    border: 1px solid #555;
    border-radius: 4px;
    margin-top: -1px;
}

QTabBar::tab {
    background-color: #3c3c3c;
    color: #d4d4d4;
    padding: 10px 20px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    border: 1px solid #555;
    border-bottom: none;
}

QTabBar::tab:hover {
    background-color: #4a4a4a;
}

QTabBar::tab:selected {
    background-color: #252525;
    color: white;
    font-weight: bold;
    border-bottom: 2px solid #0d6efd;
}

/* Group boxes */
QGroupBox {
    font-weight: bold;
    border: 2px solid #555;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 12px;
    color: #d4d4d4;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    background-color: #252525;
}

/* Progress bars */
QProgressBar {
    background-color: #2d2d2d;
    border: 1px solid #555;
    border-radius: 6px;
    text-align: center;
    color: #d4d4d4;
}

QProgressBar::chunk {
    background-color: #0d6efd;
    border-radius: 6px;
}

/* Check boxes */
QCheckBox {
    color: #d4d4d4;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #555;
    border-radius: 4px;
}

QCheckBox::indicator:checked {
    background-color: #0d6efd;
    border-color: #0d6efd;
    image: url(checkmark.png);
}

/* Radio buttons */
QRadioButton {
    color: #d4d4d4;
    spacing: 8px;
}

QRadioButton::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #555;
    border-radius: 9px;
}

QRadioButton::indicator:checked {
    background-color: #0d6efd;
    border-color: #0d6efd;
}

/* Spin boxes */
QSpinBox, QDoubleSpinBox {
    background-color: #2d2d2d;
    color: #d4d4d4;
    border: 1px solid #555;
    border-radius: 4px;
    padding: 6px 8px;
}

/* Tree widgets */
QTreeWidget {
    background-color: #2d2d2d;
    color: #d4d4d4;
    border: 1px solid #555;
    border-radius: 4px;
    padding: 2px;
}

QTreeWidget::item {
    padding: 4px 2px;
}

QTreeWidget::item:hover {
    background-color: #3a3a3a;
}

QTreeWidget::item:selected {
    background-color: #0d6efd;
    color: white;
}

/* Dialogs */
QDialog {
    background-color: #252525;
    color: #d4d4d4;
}

/* Message boxes */
QMessageBox {
    background-color: #252525;
    color: #d4d4d4;
}

QMessageBox QLabel {
    color: #d4d4d4;
}

/* Tool tips */
QToolTip {
    background-color: #3c3c3c;
    color: #d4d4d4;
    border: 1px solid #555;
    border-radius: 4px;
    padding: 6px;
}

/* Splitter */
QSplitter::handle {
    background-color: #3c3c3c;
}

QSplitter::handle:hover {
    background-color: #4a4a4a;
}

/* Status bar */
QStatusBar {
    background-color: #3c3c3c;
    color: #d4d4d4;
    border-top: 1px solid #555;
}
"""

# ---------------- Dialogs ----------------
class LoginDialog(QtWidgets.QDialog):
    def __init__(self, base_url, parent=None):
        super().__init__(parent)
        self.base_url = base_url.rstrip("/")
        self.auth_token = None
        self.setWindowTitle("Вход")
        self.resize(400, 200)
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        
        v = QtWidgets.QVBoxLayout(self)
        v.setSpacing(12)
        v.setContentsMargins(20, 20, 20, 20)
        
        title = QtWidgets.QLabel("🔐 Авторизация")
        title.setProperty("title", True)
        v.addWidget(title)
        
        form = QtWidgets.QFormLayout()
        form.setSpacing(10)
        self.user = QtWidgets.QLineEdit()
        self.user.setPlaceholderText("Введите имя пользователя")
        self.pwd = QtWidgets.QLineEdit()
        self.pwd.setEchoMode(QtWidgets.QLineEdit.Password)
        self.pwd.setPlaceholderText("Введите пароль")
        form.addRow("👤 Имя:", self.user)
        form.addRow("🔑 Пароль:", self.pwd)
        v.addLayout(form)
        
        self.status = QtWidgets.QLabel("")
        self.status.setStyleSheet("color: #ff6b6b; padding: 5px; background-color: #3c3c3c; border-radius: 4px;")
        self.status.setVisible(False)
        v.addWidget(self.status)
        
        btns = QtWidgets.QHBoxLayout()
        btns.setSpacing(10)
        ok = QtWidgets.QPushButton("🚀 Войти")
        ok.setProperty("primary", True)
        cancel = QtWidgets.QPushButton("❌ Отмена")
        btns.addStretch()
        btns.addWidget(ok)
        btns.addWidget(cancel)
        v.addLayout(btns)
        
        ok.clicked.connect(self.attempt_login)
        cancel.clicked.connect(self.reject)
        self.user.returnPressed.connect(self.pwd.setFocus)
        self.pwd.returnPressed.connect(self.attempt_login)

    def attempt_login(self):
        username = self.user.text().strip()
        password = self.pwd.text()
        
        if not username:
            self.status.setText("Введите имя пользователя")
            self.status.setVisible(True)
            return
        
        try:
            # Используем базовую аутентификацию как в API
            auth_str = f"{username}:{password}"
            auth_b64 = base64.b64encode(auth_str.encode()).decode()
            headers = {"Authorization": f"Basic {auth_b64}"}
            
            response = requests.get(
                f"{self.base_url}/api/auth/verify",
                headers=headers,
                timeout=8,
                verify=False
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("authenticated"):
                    self.auth_token = auth_b64  # Сохраняем токен для последующих запросов
                    self.accept()
                else:
                    self.status.setText("Неверные учетные данные")
                    self.status.setVisible(True)
            else:
                self.status.setText(f"Ошибка сервера: {response.status_code}")
                self.status.setVisible(True)
                
        except Exception as e:
            self.status.setText(f"Ошибка сети: {str(e)}")
            self.status.setVisible(True)

    def get_auth_token(self):
        return self.auth_token

class UserEditDialog(QtWidgets.QDialog):
    def __init__(self, base_url, auth_token, user=None, privileges=None, all_privs=None, parent=None):
        super().__init__(parent)
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        self.setWindowTitle("👤 Пользователь" + (" — Редактирование" if user else " — Создать"))
        self.resize(580, 420)
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        
        v = QtWidgets.QVBoxLayout(self)
        v.setSpacing(15)
        v.setContentsMargins(20, 20, 20, 20)
        
        title = QtWidgets.QLabel("👤 Управление пользователем" if user else "➕ Создание пользователя")
        title.setProperty("title", True)
        v.addWidget(title)
        
        form = QtWidgets.QFormLayout()
        form.setSpacing(10)
        self.username = QtWidgets.QLineEdit()
        self.username.setPlaceholderText("Имя пользователя")
        self.password = QtWidgets.QLineEdit()
        self.password.setPlaceholderText("Пароль (оставьте пустым для неизменения)" if user else "Пароль (обязательно)")
        self.password.setEchoMode(QtWidgets.QLineEdit.Password)
        form.addRow("👤 Имя:", self.username)
        form.addRow("🔑 Пароль:", self.password)
        v.addLayout(form)
        
        v.addWidget(QtWidgets.QLabel("🔐 Привилегии:"))
        
        self.priv_list = QtWidgets.QListWidget()
        self.priv_list.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        self.priv_list.setMinimumHeight(150)
        v.addWidget(self.priv_list, 1)
        
        h = QtWidgets.QHBoxLayout()
        h.setSpacing(10)
        ok = QtWidgets.QPushButton("💾 Сохранить")
        ok.setProperty("primary", True)
        cancel = QtWidgets.QPushButton("❌ Отмена")
        h.addStretch()
        h.addWidget(ok)
        h.addWidget(cancel)
        v.addLayout(h)
        
        ok.clicked.connect(self.do_save)
        cancel.clicked.connect(self.reject)
        
        # Заполняем список привилегий
        all_privs = all_privs or []
        for p in all_privs:
            it = QtWidgets.QListWidgetItem(f"✓ {p}")
            it.setFlags(it.flags() | QtCore.Qt.ItemIsUserCheckable)
            it.setCheckState(QtCore.Qt.Unchecked)
            self.priv_list.addItem(it)
        
        if user:
            self.username.setText(user)
            self.username.setEnabled(False)
            if privileges:
                for i in range(self.priv_list.count()):
                    item = self.priv_list.item(i)
                    if item.text().replace("✓ ", "") in privileges:
                        item.setCheckState(QtCore.Qt.Checked)

    def do_save(self):
        name = self.username.text().strip()
        pwd = self.password.text()
        selected = [self.priv_list.item(i).text().replace("✓ ", "") 
                    for i in range(self.priv_list.count()) 
                    if self.priv_list.item(i).checkState() == QtCore.Qt.Checked]
        
        if not name:
            QtWidgets.QMessageBox.warning(self, "Ошибка", "Введите имя пользователя")
            return
        
        if self.username.isEnabled() and not pwd:  # Создание нового
            QtWidgets.QMessageBox.warning(self, "Ошибка", "При создании пользователя пароль обязателен!")
            return
        
        try:
            headers = {"Authorization": f"Basic {self.auth_token}"}
            
            if self.username.isEnabled():  # Создание
                payload = {
                    "username": name,
                    "password": pwd,
                    "privileges": selected
                }
                response = requests.post(
                    f"{self.base_url}/api/users/create",
                    json=payload,
                    headers=headers,
                    timeout=8,
                    verify=False
                )
            else:  # Редактирование
                payload = {
                    "username": name,
                    "privileges": selected
                }
                if pwd:
                    payload["password"] = pwd
                
                response = requests.post(
                    f"{self.base_url}/api/users/edit",
                    json=payload,
                    headers=headers,
                    timeout=8,
                    verify=False
                )
            
            if response.status_code in (200, 201):
                QtWidgets.QMessageBox.information(self, "Успех", "Настройки сохранены")
                self.accept()
            else:
                QtWidgets.QMessageBox.warning(self, "Ошибка", 
                    f"Не удалось сохранить: {response.status_code}\n{response.text[:200]}")
                
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Ошибка", f"Ошибка сети: {str(e)}")

class BlacklistDialog(QtWidgets.QDialog):
    def __init__(self, base_url, auth_token, username, current_blacklist=None, parent=None):
        super().__init__(parent)
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        self.username = username
        
        self.setWindowTitle(f"🚫 Черный список команд - {username}")
        self.resize(600, 400)
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        
        title = QtWidgets.QLabel(f"Черный список команд для пользователя: {username}")
        title.setProperty("title", True)
        layout.addWidget(title)
        
        desc = QtWidgets.QLabel(
            "Добавьте команды или выражения, которые пользователь не сможет выполнять.\n"
            "Примеры: 'format', 'del ', 'shutdown', 'rmdir'"
        )
        desc.setStyleSheet("color: #aaa; padding: 5px;")
        layout.addWidget(desc)
        
        layout.addWidget(QtWidgets.QLabel("Запрещенные команды:"))
        
        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        layout.addWidget(self.list_widget, 1)
        
        add_layout = QtWidgets.QHBoxLayout()
        self.command_input = QtWidgets.QLineEdit()
        self.command_input.setPlaceholderText("Введите команду для добавления в черный список...")
        add_button = QtWidgets.QPushButton("➕ Добавить")
        add_button.clicked.connect(self.add_command)
        
        add_layout.addWidget(self.command_input, 1)
        add_layout.addWidget(add_button)
        layout.addLayout(add_layout)
        
        button_layout = QtWidgets.QHBoxLayout()
        
        delete_button = QtWidgets.QPushButton("🗑️ Удалить выбранное")
        delete_button.clicked.connect(self.delete_selected)
        delete_button.setProperty("danger", True)
        
        clear_button = QtWidgets.QPushButton("🧹 Очистить список")
        clear_button.clicked.connect(self.clear_list)
        
        button_layout.addWidget(delete_button)
        button_layout.addWidget(clear_button)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        bottom_layout = QtWidgets.QHBoxLayout()
        save_button = QtWidgets.QPushButton("💾 Сохранить")
        save_button.setProperty("primary", True)
        cancel_button = QtWidgets.QPushButton("❌ Отмена")
        
        save_button.clicked.connect(self.save_blacklist)
        cancel_button.clicked.connect(self.reject)
        
        bottom_layout.addStretch()
        bottom_layout.addWidget(save_button)
        bottom_layout.addWidget(cancel_button)
        layout.addLayout(bottom_layout)
        
        if current_blacklist:
            for cmd in current_blacklist:
                self.list_widget.addItem(cmd)
    
    def add_command(self):
        cmd = self.command_input.text().strip()
        if cmd:
            self.list_widget.addItem(cmd)
            self.command_input.clear()
    
    def delete_selected(self):
        for item in self.list_widget.selectedItems():
            self.list_widget.takeItem(self.list_widget.row(item))
    
    def clear_list(self):
        self.list_widget.clear()
    
    def save_blacklist(self):
        commands = []
        for i in range(self.list_widget.count()):
            commands.append(self.list_widget.item(i).text())
        
        try:
            headers = {"Authorization": f"Basic {self.auth_token}"}
            response = requests.put(
                f"{self.base_url}/api/user/{self.username}/blacklist",
                json={"commands": commands},
                headers=headers,
                timeout=10,
                verify=False
            )
            
            if response.status_code == 200:
                QtWidgets.QMessageBox.information(self, "Успех", "Черный список сохранен")
                self.accept()
            else:
                QtWidgets.QMessageBox.warning(self, "Ошибка", 
                    f"Ошибка сохранения: {response.status_code}\n{response.text}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Ошибка", f"Ошибка сети: {str(e)}")

class CreateTaskDialog(QtWidgets.QDialog):
    def __init__(self, base_url, auth_token, agents_dict, parent=None):
        super().__init__(parent)
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        self.setWindowTitle("➕ Создать задачу")
        self.resize(700, 650)
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        
        v = QtWidgets.QVBoxLayout(self)
        v.setSpacing(15)
        v.setContentsMargins(20, 20, 20, 20)
        
        title = QtWidgets.QLabel("🎯 Создание новой задачи")
        title.setProperty("title", True)
        v.addWidget(title)
        
        type_layout = QtWidgets.QHBoxLayout()
        type_layout.addWidget(QtWidgets.QLabel("📝 Тип задачи:"))
        
        self.task_type = QtWidgets.QComboBox()
        self.task_type.addItems(["RUN_CMD", "UPLOAD_FILE"])
        self.task_type.currentTextChanged.connect(self.on_task_type_changed)
        type_layout.addWidget(self.task_type, 1)
        v.addLayout(type_layout)
        
        self.stacked_widget = QtWidgets.QStackedWidget()
        v.addWidget(self.stacked_widget, 1)
        
        self.run_cmd_panel = self.create_run_cmd_panel()
        self.stacked_widget.addWidget(self.run_cmd_panel)
        
        self.upload_panel = self.create_upload_panel()
        self.stacked_widget.addWidget(self.upload_panel)
        
        v.addWidget(QtWidgets.QLabel("🖥️ Целевые агенты:"))
        
        self.agents_area = QtWidgets.QWidget()
        self.agents_layout = QtWidgets.QVBoxLayout(self.agents_area)
        self.agents_layout.setContentsMargins(5, 5, 5, 5)
        self.agent_checks = {}
        
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.agents_area)
        scroll.setFixedHeight(120)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        v.addWidget(scroll)
        
        timeout_layout = QtWidgets.QHBoxLayout()
        timeout_layout.addWidget(QtWidgets.QLabel("⏱️ Таймаут:"))
        self.timeout = QtWidgets.QSpinBox()
        self.timeout.setRange(10, 86400)
        self.timeout.setValue(300)
        self.timeout.setSuffix(" сек")
        timeout_layout.addWidget(self.timeout, 1)
        v.addLayout(timeout_layout)
        
        h = QtWidgets.QHBoxLayout()
        h.setSpacing(10)
        btn_create = QtWidgets.QPushButton("🚀 Создать")
        btn_create.setProperty("primary", True)
        btn_cancel = QtWidgets.QPushButton("❌ Отмена")
        h.addStretch()
        h.addWidget(btn_create)
        h.addWidget(btn_cancel)
        v.addLayout(h)
        
        btn_create.clicked.connect(self.create_task)
        btn_cancel.clicked.connect(self.reject)
        
        self.agents_dict = agents_dict
        self.populate_agents(agents_dict)
        self.stacked_widget.setCurrentIndex(0)
    
    def create_run_cmd_panel(self):
        panel = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setSpacing(10)
        
        # Команда
        layout.addWidget(QtWidgets.QLabel("💻 Команда:"))
        self.cmd = QtWidgets.QTextEdit()
        self.cmd.setPlaceholderText("Введите команду или скрипт для выполнения...")
        self.cmd.setMaximumHeight(180)  # Увеличенная высота
        self.cmd.setMinimumHeight(120)  # Минимальная высота
        layout.addWidget(self.cmd)
        
        # Shell
        shell_layout = QtWidgets.QHBoxLayout()
        shell_layout.addWidget(QtWidgets.QLabel("🐚 Shell:"))
        self.shell = QtWidgets.QComboBox()
        self.shell.addItems(["cmd", "powershell"])
        shell_layout.addWidget(self.shell, 1)
        layout.addLayout(shell_layout)
        
        # Локальный файл для отправки на агента
        file_group = QtWidgets.QGroupBox("📎 Локальный файл (опционально)")
        file_layout = QtWidgets.QVBoxLayout(file_group)
        
        self.filepath_local = QtWidgets.QLineEdit()
        self.filepath_local.setPlaceholderText("Выберите локальный файл для отправки на агента...")
        self.btn_browse = QtWidgets.QPushButton("📁 Обзор")
        self.btn_browse.setProperty("primary", True)
        
        hb = QtWidgets.QHBoxLayout()
        hb.setSpacing(10)
        hb.addWidget(self.filepath_local, 1)
        hb.addWidget(self.btn_browse)
        file_layout.addLayout(hb)
        
        layout.addWidget(file_group)
        self.btn_browse.clicked.connect(self.pick_file)
        
        # Путь сохранения на агенте
        layout.addWidget(QtWidgets.QLabel("💾 Путь сохранения на агенте:"))
        self.save_path = QtWidgets.QLineEdit()
        self.save_path.setPlaceholderText("C:\\path\\to\\save\\file.ext (опционально)")
        layout.addWidget(self.save_path)
        
        layout.addStretch()
        return panel
    
    def create_upload_panel(self):
        panel = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setSpacing(10)
        
        layout.addWidget(QtWidgets.QLabel("📤 Путь к файлу на агенте:"))
        self.src_path = QtWidgets.QLineEdit()
        self.src_path.setPlaceholderText("C:\\path\\to\\file.ext")
        layout.addWidget(self.src_path)
        
        layout.addWidget(QtWidgets.QLabel("💾 Имя файла на сервере:"))
        self.target_name = QtWidgets.QLineEdit()
        self.target_name.setPlaceholderText("file.ext (если оставить пустым, будет использовано исходное имя)")
        layout.addWidget(self.target_name)
        
        layout.addStretch()
        return panel
    
    def on_task_type_changed(self, new_type):
        if new_type == "RUN_CMD":
            self.stacked_widget.setCurrentWidget(self.run_cmd_panel)
        else:
            self.stacked_widget.setCurrentWidget(self.upload_panel)
    
    def pick_file(self):
        p, _ = QtWidgets.QFileDialog.getOpenFileName(self, "📁 Выбрать файл")
        if p:
            self.filepath_local.setText(p)
            import os
            filename = os.path.basename(p)
            if not self.save_path.text():
                self.save_path.setText(f"C:\\Windows\\Temp\\{filename}")
    
    def populate_agents(self, agents):
        for i in reversed(range(self.agents_layout.count())):
            w = self.agents_layout.itemAt(i).widget()
            if w:
                w.deleteLater()
        self.agent_checks = {}
        
        for aid, info in sorted(agents.items()):
            cb = QtWidgets.QCheckBox(f"🖥️ {info.get('name',aid)} ({aid[:8]}...) - {info.get('ip','')}")
            self.agents_layout.addWidget(cb)
            self.agent_checks[aid] = cb
        
        select_all_cb = QtWidgets.QCheckBox("✅ Выбрать всех")
        select_all_cb.stateChanged.connect(self.toggle_all_agents)
        self.agents_layout.addWidget(select_all_cb)
    
    def toggle_all_agents(self, state):
        for cb in self.agent_checks.values():
            cb.setChecked(state == QtCore.Qt.Checked)
    
    def create_task(self):
        ttype = self.task_type.currentText()
        timeout = int(self.timeout.value())
        selected = [aid for aid, cb in self.agent_checks.items() if cb.isChecked()]
        
        if not selected:
            QtWidgets.QMessageBox.warning(self, "⚠️ Ошибка", "Выберите хотя бы одного агента")
            return
        
        headers = {"Authorization": f"Basic {self.auth_token}"}
        
        if ttype == "UPLOAD_FILE":
            src_path = self.src_path.text().strip()
            target_name = self.target_name.text().strip()
            
            if not src_path:
                QtWidgets.QMessageBox.warning(self, "⚠️ Ошибка", "Укажите путь к файлу на агенте")
                return
            
            if not target_name:
                import os
                target_name = os.path.basename(src_path)
                if not target_name:
                    QtWidgets.QMessageBox.warning(self, "⚠️ Ошибка", 
                        "Не удалось определить имя файла из пути. Укажите 'Имя файла на сервере' вручную.")
                    return
            
            payload = {
                "task_type": "UPLOAD_FILE",
                "source_path_upload": src_path,
                "target_name": target_name,
                "timeout": timeout,
                "agents": selected
            }
            
            try:
                response = requests.post(
                    f"{self.base_url}/api/tasks/create",
                    json=payload,
                    headers=headers,
                    timeout=15,
                    verify=False
                )
                
                if response.status_code in (200, 201):
                    QtWidgets.QMessageBox.information(self, "✅ Успех", "Задача на загрузку файла создана")
                    self.accept()
                else:
                    QtWidgets.QMessageBox.warning(self, "⚠️ Ошибка", 
                        f"Ошибка создания задачи: {response.status_code}\n{response.text[:200]}")
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "⚠️ Ошибка", f"Ошибка сети: {str(e)}")
            return
        
        elif ttype == "RUN_CMD":
            cmd = self.cmd.toPlainText().strip()
            shell = self.shell.currentText()
            save_path = self.save_path.text().strip()
            local_file_path = self.filepath_local.text().strip()
            
            if not cmd and not local_file_path:
                QtWidgets.QMessageBox.warning(self, "⚠️ Ошибка", 
                    "Введите команду или выберите файл для отправки")
                return
            
            payload = {
                "task_type": "RUN_CMD",
                "cmd": cmd,
                "timeout": timeout,
                "shell": shell,
                "agents": selected
            }
            
            if save_path:
                payload["save_path"] = save_path
            
            files = None
            if local_file_path:
                try:
                    files = {'file': open(local_file_path, 'rb')}
                    if not save_path:
                        import os
                        filename = os.path.basename(local_file_path)
                        payload["save_path"] = f"C:\\Windows\\Temp\\{filename}"
                except Exception as e:
                    QtWidgets.QMessageBox.warning(self, "⚠️ Ошибка", 
                        f"Не удалось открыть файл: {str(e)}")
                    return
            
            try:
                if files:
                    file_data = {'file': files['file']}
                    response = requests.post(
                        f"{self.base_url}/api/tasks/create",
                        data=payload,
                        files=file_data,
                        headers=headers,
                        timeout=20,
                        verify=False
                    )
                    files['file'].close()
                else:
                    response = requests.post(
                        f"{self.base_url}/api/tasks/create",
                        json=payload,
                        headers=headers,
                        timeout=12,
                        verify=False
                    )
                
                if response.status_code in (200, 201):
                    QtWidgets.QMessageBox.information(self, "✅ Успех", "Задача создана")
                    self.accept()
                else:
                    QtWidgets.QMessageBox.warning(self, "⚠️ Ошибка", 
                        f"Ошибка создания задачи: {response.status_code}\n{response.text[:200]}")
            except Exception as e:
                if files:
                    files['file'].close()
                QtWidgets.QMessageBox.warning(self, "⚠️ Ошибка", str(e))

class AgentInfoDialog(QtWidgets.QDialog):
    def __init__(self, base_url, auth_token, agent_id, parent=None):
        super().__init__(parent)
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        self.agent = agent_id
        self.setWindowTitle(f"ℹ️ Информация агента: {agent_id[:12]}...")
        self.resize(680, 520)
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        
        v = QtWidgets.QVBoxLayout(self)
        v.setSpacing(15)
        v.setContentsMargins(20, 20, 20, 20)
        
        title = QtWidgets.QLabel(f"🖥️ Агент: {agent_id}")
        title.setProperty("title", True)
        v.addWidget(title)
        
        self.txt = QtWidgets.QTextEdit()
        self.txt.setReadOnly(True)
        self.txt.setFont(QtGui.QFont("Consolas", 10))
        v.addWidget(self.txt, 1)
        
        btn = QtWidgets.QPushButton("🔄 Обновить")
        btn.setProperty("primary", True)
        v.addWidget(btn)
        btn.clicked.connect(self.load)
        
        self.load()
    
    def load(self):
        try:
            headers = {"Authorization": f"Basic {self.auth_token}"}
            response = requests.get(
                f"{self.base_url}/api/agents/{self.agent}",
                headers=headers,
                timeout=8,
                verify=False
            )
            
            if response.status_code == 200:
                j = response.json()
                out = []
                out.append("=" * 50)
                out.append("📋 МЕТАДАННЫЕ АГЕНТА")
                out.append("=" * 50)
                for k, v in j.get("agent", {}).items():
                    out.append(f"  {k:20}: {v}")
                out.append("\n" + "=" * 50)
                out.append("📊 ТЕЛЕМЕТРИЯ")
                out.append("=" * 50)
                out.append(json.dumps(j.get("telemetry", {}), indent=2, ensure_ascii=False))
                self.txt.setPlainText("\n".join(out))
            else:
                self.txt.setPlainText(f"❌ Ошибка {response.status_code}\n{response.text}")
        except Exception as e:
            self.txt.setPlainText("❌ Ошибка: " + str(e))

class MonitorDialog(QtWidgets.QDialog):
    def __init__(self, base_url, auth_token, agent_id, type_, path="C:\\", parent=None):
        super().__init__(parent)
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        self.agent = agent_id
        self.type = type_
        self.path = path
        self.current_path = path
        
        icon = "📋" if type_ == "PROCESSES" else "📂"
        self.setWindowTitle(f"{icon} Мониторинг {agent_id[:8]}... / {type_}")
        self.resize(950, 680)
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        
        top_layout = QtWidgets.QHBoxLayout()
        
        self.btn_back = QtWidgets.QPushButton("← Назад")
        self.btn_back.setEnabled(False)
        self.btn_back.setFixedWidth(120)
        self.btn_back.clicked.connect(self.on_back_clicked)
        top_layout.addWidget(self.btn_back)
        
        self.path_input = QtWidgets.QLineEdit()
        self.path_input.setPlaceholderText("Введите путь (C:\\Windows или /home)")
        self.path_input.returnPressed.connect(self.on_path_entered)
        
        self.is_editing_path = False
        self.path_input.textChanged.connect(self.on_path_text_changed)
        
        top_layout.addWidget(self.path_input, 1)
        
        self.btn_go = QtWidgets.QPushButton("Перейти")
        self.btn_go.clicked.connect(self.on_path_entered)
        top_layout.addWidget(self.btn_go)
        
        layout.addLayout(top_layout)
        
        self.lbl = QtWidgets.QLabel("⏳ Инициализация...")
        self.lbl.setStyleSheet("font-weight: bold; padding: 8px; background-color: #3c3c3c; border-radius: 4px;")
        layout.addWidget(self.lbl)
        
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        splitter.setStyleSheet("QSplitter::handle { background-color: #555; }")
        
        self.proc_table = QtWidgets.QTableWidget(0, 3)
        self.proc_table.setHorizontalHeaderLabels(["🆔 PID", "📛 Имя", "🧵 Потоки"])
        self.proc_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.proc_table.horizontalHeader().setStretchLastSection(True)
        splitter.addWidget(self.proc_table)
        
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["📁 Имя", "📄 Тип", "📦 Размер"])
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        splitter.addWidget(self.tree)
        
        splitter.setSizes([400, 400])
        layout.addWidget(splitter, 1)
        
        bottom_layout = QtWidgets.QHBoxLayout()
        
        self.log = QtWidgets.QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(80)
        self.log.setPlaceholderText("Лог событий...")
        bottom_layout.addWidget(self.log, 1)
        
        self.btn_stop = QtWidgets.QPushButton("⏹️ Остановить")
        self.btn_stop.setProperty("danger", True)
        self.btn_stop.setFixedWidth(150)
        bottom_layout.addWidget(self.btn_stop)
        
        layout.addLayout(bottom_layout)
        
        self.monitoring_task_id = None
        self.btn_stop.clicked.connect(self.stop_and_close)
        self.tree.itemDoubleClicked.connect(self.on_tree_double)
        
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self.poll_once)
        
        QtCore.QTimer.singleShot(100, self.create_initial_task)
    
    def create_initial_task(self):
        headers = {"Authorization": f"Basic {self.auth_token}"}
        payload = {
            "task_type": self.type,
            "cmd": self.path,
            "timeout": 0,
            "agents": [self.agent]
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/api/tasks/create",
                json=payload,
                headers=headers,
                timeout=10,
                verify=False
            )
            
            if response.status_code in (200, 201):
                self.log_append("✅ Задача мониторинга создана")
                data = response.json()
                self.monitoring_task_id = data.get("task_id")
                QtCore.QTimer.singleShot(2000, self.find_monitoring_task)
                self.timer.start(2000)
            else:
                self.log_append(f"❌ Ошибка создания задачи: {response.status_code}")
        except Exception as e:
            self.log_append(f"❌ Ошибка создания задачи: {str(e)}")
    
    def find_monitoring_task(self):
        headers = {"Authorization": f"Basic {self.auth_token}"}
        try:
            response = requests.get(
                f"{self.base_url}/api/tasks",
                headers=headers,
                timeout=6,
                verify=False
            )
            
            if response.status_code == 200:
                tasks = response.json()
                for task in reversed(tasks):
                    if (task.get("task_type") == self.type and 
                        self.agent in task.get("agent_ids", []) and
                        task.get("status", {}).get(self.agent) in ["PENDING", "RUNNING"]):
                        
                        self.monitoring_task_id = task.get("id")
                        current_path = task.get("cmd", self.path)
                        
                        self.current_path = current_path
                        self.path_input.setText(current_path if current_path != "ROOT" else "")
                        self.lbl.setText(f"📁 Текущий путь: {current_path}")
                        
                        self.log_append(f"✅ Найдена задача: {self.monitoring_task_id}")
                        return True
        except Exception as e:
            print(f"[DEBUG] Исключение в find_monitoring_task: {e}")
        
        return False
    
    def on_back_clicked(self):
        if self.monitoring_task_id and self.current_path and self.current_path != "ROOT":
            parts = self.current_path.rstrip('\\').split('\\')
            if len(parts) > 1:
                new_path = '\\'.join(parts[:-1])
                if not new_path:
                    new_path = "ROOT"
                self.update_monitoring_path(new_path)
    
    def on_path_entered(self):
        path = self.path_input.text().strip()
        if path:
            if path.startswith("/"):
                path = "C:" + path.replace("/", "\\")
            self.is_editing_path = False
            self.update_monitoring_path(path)
    
    def update_monitoring_path(self, new_path):
        if not self.monitoring_task_id:
            self.log_append("⚠️ ID задачи не найден")
            return
        
        headers = {"Authorization": f"Basic {self.auth_token}"}
        payload = {
            "task_id": self.monitoring_task_id,
            "new_path": new_path,
            "agent_id": self.agent
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/api/tasks/update_path",
                json=payload,
                headers=headers,
                timeout=8,
                verify=False
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    self.log_append(f"✅ Путь обновлен: {new_path}")
                    self.current_path = new_path
                    self.lbl.setText(f"📁 Текущий путь: {new_path}")
                    self.update_back_button()
                else:
                    self.log_append(f"⚠️ Ошибка обновления пути: {data.get('error', 'unknown')}")
            else:
                self.log_append(f"⚠️ Ошибка обновления пути: {response.status_code}")
                
        except Exception as e:
            self.log_append(f"⚠️ Ошибка обновления пути: {str(e)}")
    
    def update_back_button(self):
        if self.current_path and self.current_path != "ROOT":
            self.btn_back.setEnabled(True)
        else:
            self.btn_back.setEnabled(False)
    
    def on_tree_double(self, item, col):
        d = item.data(0, QtCore.Qt.UserRole) or {}
        if d.get("is_dir"):
            folder_name = d.get("name", "")
            if self.current_path == "ROOT" or self.current_path == "Мой компьютер":
                new_path = folder_name
            else:
                if self.current_path.endswith("\\"):
                    new_path = self.current_path + folder_name
                else:
                    new_path = self.current_path + "\\" + folder_name
            self.update_monitoring_path(new_path)
        else:
            self.log_append(f"📄 Файл: {d.get('name', '')}")
    
    def on_path_text_changed(self, text):
        self.is_editing_path = True
    
    def poll_once(self):
        if not self.monitoring_task_id:
            if not self.find_monitoring_task():
                return
        
        headers = {"Authorization": f"Basic {self.auth_token}"}
        try:
            response = requests.get(
                f"{self.base_url}/api/tasks/{self.monitoring_task_id}/monitoring?agent_id={self.agent}",
                headers=headers,
                timeout=6,
                verify=False
            )
            
            if response.status_code == 200:
                data = response.json()
                if self.type == "PROCESSES":
                    self.render_procs(data)
                else:
                    self.render_fs(data)
                    current_path = data.get("path", "")
                    if current_path and not self.is_editing_path:
                        self.current_path = current_path
                        if self.path_input.text() != current_path:
                            self.path_input.blockSignals(True)
                            self.path_input.setText(current_path if current_path != "Мой компьютер" else "")
                            self.path_input.blockSignals(False)
                        self.lbl.setText(f"📁 Текущий путь: {current_path}")
                        self.update_back_button()
            else:
                self.get_data_from_task()
        except Exception as e:
            print(f"[DEBUG] Ошибка опроса: {e}")
            self.get_data_from_task()
    
    def get_data_from_task(self):
        if not self.monitoring_task_id:
            return
        
        headers = {"Authorization": f"Basic {self.auth_token}"}
        try:
            response = requests.get(
                f"{self.base_url}/api/tasks/{self.monitoring_task_id}",
                headers=headers,
                timeout=6,
                verify=False
            )
            
            if response.status_code == 200:
                task_info = response.json()
                results = task_info.get("results", {}).get(self.agent, {})
                if results and isinstance(results, dict):
                    if self.type == "PROCESSES":
                        self.render_procs(results.get("data", []))
                    else:
                        self.render_fs(results)
                        current_path = results.get("path", "")
                        if current_path and not self.is_editing_path:
                            self.current_path = current_path
                            if self.path_input.text() != current_path:
                                self.path_input.blockSignals(True)
                                self.path_input.setText(current_path if current_path != "Мой компьютер" else "")
                                self.path_input.blockSignals(False)
                            self.lbl.setText(f"📁 Текущий путь: {current_path}")
                            self.update_back_button()
        except Exception as e:
            print(f"[DEBUG] Ошибка получения данных из задачи: {e}")
    
    def render_procs(self, data):
        if not isinstance(data, list):
            return
        self.proc_table.setRowCount(0)
        for p in data:
            r = self.proc_table.rowCount()
            self.proc_table.insertRow(r)
            self.proc_table.setItem(r, 0, QtWidgets.QTableWidgetItem(str(p.get("pid", ""))))
            self.proc_table.setItem(r, 1, QtWidgets.QTableWidgetItem(str(p.get("name", ""))))
            self.proc_table.setItem(r, 2, QtWidgets.QTableWidgetItem(str(p.get("threads", ""))))
    
    def render_fs(self, data):
        if not isinstance(data, dict):
            return
        self.tree.clear()
        items = data.get("items", [])
        for it in items:
            typ = "📁 ДИРЕКТОРИЯ" if it.get("is_dir") else "📄 ФАЙЛ"
            size = "" if it.get("is_dir") else self.format_size(it.get("size", 0))
            node = QtWidgets.QTreeWidgetItem([it.get("name", ""), typ, size])
            node.setIcon(0, QtWidgets.QApplication.style().standardIcon(
                QtWidgets.QStyle.SP_DirIcon if it.get("is_dir") 
                else QtWidgets.QStyle.SP_FileIcon
            ))
            node.setData(0, QtCore.Qt.UserRole, it)
            self.tree.addTopLevelItem(node)
    
    def format_size(self, size):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    
    def log_append(self, s):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log.append(f"[{timestamp}] {s}")
    
    def stop_and_close(self):
        headers = {"Authorization": f"Basic {self.auth_token}"}
        try:
            response = requests.post(
                f"{self.base_url}/api/tasks/{self.monitoring_task_id}/stop",
                json={"agent_id": self.agent},
                headers=headers,
                timeout=6,
                verify=False
            )
            self.log_append("✅ Сессия мониторинга остановлена")
        except Exception as e:
            self.log_append("⚠️ Ошибка остановки: " + str(e))
        self.timer.stop()
        self.accept()

class LogsDialog(QtWidgets.QDialog):
    def __init__(self, base_url, auth_token, parent=None):
        super().__init__(parent)
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        self.setWindowTitle("📜 Логи сервера")
        self.resize(950, 650)
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        
        v = QtWidgets.QVBoxLayout(self)
        v.setSpacing(15)
        v.setContentsMargins(20, 20, 20, 20)
        
        title = QtWidgets.QLabel("📜 Просмотр логов сервера")
        title.setProperty("title", True)
        v.addWidget(title)
        
        h = QtWidgets.QHBoxLayout()
        h.setSpacing(10)
        self.sel = QtWidgets.QComboBox()
        self.sel.addItems(["👁️ Аудит", "🌐 HTTP", "⚙️ Технические"])
        self.btn = QtWidgets.QPushButton("🔄 Обновить")
        self.btn.setProperty("primary", True)
        h.addWidget(QtWidgets.QLabel("📂 Категория:"))
        h.addWidget(self.sel, 1)
        h.addWidget(self.btn)
        v.addLayout(h)
        
        self.text = QtWidgets.QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setFont(QtGui.QFont("Consolas", 10))
        v.addWidget(self.text, 1)
        
        self.btn.clicked.connect(self.load)
        self.load()
    
    def load(self):
        cat_map = {
            "👁️ Аудит": "audit",
            "🌐 HTTP": "http", 
            "⚙️ Технические": "tech"
        }
        cat = cat_map.get(self.sel.currentText(), "audit")
        
        try:
            headers = {"Authorization": f"Basic {self.auth_token}"}
            response = requests.get(
                f"{self.base_url}/api/logs?which={cat}",
                headers=headers,
                timeout=8,
                verify=False
            )
            
            if response.status_code == 200:
                arr = response.json()
                lines = []
                for i, x in enumerate(arr):
                    try:
                        lines.append(f"[{i+1:04d}] {json.dumps(x, ensure_ascii=False)}")
                    except:
                        lines.append(f"[{i+1:04d}] {str(x)}")
                self.text.setPlainText("\n".join(lines))
                self.text.moveCursor(QtGui.QTextCursor.End)
            else:
                self.text.setPlainText(f"❌ Ошибка {response.status_code}\n{response.text}")
        except Exception as e:
            self.text.setPlainText("❌ Ошибка: " + str(e))

# ---------------- Main Window ----------------
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle(" Control Node — Desktop")
        self.resize(1280, 880)
        self.servers = load_servers()
        self.current_base = None
        self.auth_token = None
        self.current_user = None
        
        self.setStyleSheet(DARK_THEME)
        
        self.clock_timer = QtCore.QTimer(self)
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(1000)  # Обновление каждую секунду
        
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        h = QtWidgets.QHBoxLayout(central)
        h.setSpacing(20)
        h.setContentsMargins(20, 20, 20, 20)
        
        # left: servers panel
        left_panel = QtWidgets.QFrame()
        left_panel.setFrameShape(QtWidgets.QFrame.StyledPanel)
        left_panel.setMinimumWidth(280)
        left_panel.setMaximumWidth(350)
        left = QtWidgets.QVBoxLayout(left_panel)
        left.setSpacing(10)
        left.setContentsMargins(15, 15, 15, 15)
        
        hdr = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("🌐 Серверы")
        title.setProperty("title", True)
        hdr.addWidget(title)
        hdr.addStretch()

        btn_add = QtWidgets.QToolButton()
        btn_add.setText("+")
        btn_add.setToolTip("Добавить сервер")
        btn_add.setFixedSize(32, 32)
        btn_add.setStyleSheet("""
            QToolButton {
                font-size: 16pt;
                font-weight: bold;
                border: 1px solid #555;
                border-radius: 4px;
                background-color: #3c3c3c;
            }
            QToolButton:hover {
                background-color: #4a4a4a;
                border-color: #666;
            }
        """)

        btn_edit = QtWidgets.QToolButton()
        btn_edit.setText("✎")
        btn_edit.setToolTip("Редактировать")
        btn_edit.setFixedSize(32, 32)
        btn_edit.setStyleSheet("""
            QToolButton {
                font-size: 14pt;
                border: 1px solid #555;
                border-radius: 4px;
                background-color: #3c3c3c;
            }
            QToolButton:hover {
                background-color: #4a4a4a;
                border-color: #666;
            }
        """)

        btn_del = QtWidgets.QToolButton()
        btn_del.setText("×")
        btn_del.setToolTip("Удалить")
        btn_del.setFixedSize(32, 32)
        btn_del.setStyleSheet("""
            QToolButton {
                font-size: 16pt;
                font-weight: bold;
                color: #ff6b6b;
                border: 1px solid #ff6b6b;
                border-radius: 4px;
                background-color: #3c3c3c;
            }
            QToolButton:hover {
                background-color: #ff4444;
                color: white;
                border-color: #ff0000;
            }
        """)

        hdr.addWidget(btn_add)
        hdr.addWidget(btn_edit)
        hdr.addWidget(btn_del)
        left.addLayout(hdr)
        
        self.list_servers = QtWidgets.QListWidget()
        self.list_servers.setAlternatingRowColors(True)
        left.addWidget(self.list_servers, 1)
        
        self.btn_connect = QtWidgets.QPushButton("🔗 Подключиться")
        self.btn_connect.setProperty("primary", True)
        left.addWidget(self.btn_connect)
        
        self.lbl_status = QtWidgets.QLabel("🟡 Готов к подключению")
        self.lbl_status.setStyleSheet("padding: 10px; background-color: #3c3c3c; border-radius: 6px;")
        left.addWidget(self.lbl_status)
        
        h.addWidget(left_panel)
        
        # right: main content
        self.stack = QtWidgets.QStackedWidget()
        h.addWidget(self.stack, 1)
        
        # Empty state
        empty = QtWidgets.QWidget()
        e_l = QtWidgets.QVBoxLayout(empty)
        e_l.setAlignment(QtCore.Qt.AlignCenter)
        e_l.setSpacing(20)
        
        icon = QtWidgets.QLabel("🌐")
        icon.setStyleSheet("font-size: 72pt;")
        icon.setAlignment(QtCore.Qt.AlignCenter)
        e_l.addWidget(icon)
        
        title = QtWidgets.QLabel("Control Node Desktop")
        title.setProperty("title", True)
        title.setAlignment(QtCore.Qt.AlignCenter)
        e_l.addWidget(title)
        
        desc = QtWidgets.QLabel("Выберите сервер из списка и нажмите 'Подключиться'")
        desc.setAlignment(QtCore.Qt.AlignCenter)
        desc.setStyleSheet("color: #aaa; font-size: 11pt;")
        e_l.addWidget(desc)
        
        self.stack.addWidget(empty)
        
        # Connected state
        page = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(page)
        v.setSpacing(15)
        
        top_bar = QtWidgets.QFrame()
        top_bar.setStyleSheet("background-color: #3c3c3c; border-radius: 8px; padding: 15px;")
        top = QtWidgets.QHBoxLayout(top_bar)
        
        # Левая часть: описание сервера
        self.lbl_srvdesc = QtWidgets.QLabel("")
        self.lbl_srvdesc.setProperty("title", True)
        top.addWidget(self.lbl_srvdesc)
        
        # Центр: часы
        self.lbl_clock = QtWidgets.QLabel()
        self.lbl_clock.setProperty("title", True)
        self.lbl_clock.setStyleSheet("""
            QLabel {
                color: #0d6efd;
                font-weight: bold;
                font-size: 11pt;
                font-family: 'Consolas', 'Monospace';
                padding: 5px 10px;
                background-color: #252525;
                border-radius: 6px;
                border: 1px solid #0d6efd;
            }
        """)
        self.lbl_clock.setAlignment(QtCore.Qt.AlignCenter)
        top.addWidget(self.lbl_clock)
        
        # Правая часть: кнопки
        top.addStretch()
        
        btn_refresh = QtWidgets.QPushButton("🔄 Обновить")
        btn_refresh.setProperty("primary", True)
        btn_logout = QtWidgets.QPushButton("🚪 Выйти")
        btn_shutdown = QtWidgets.QPushButton("⏻ Выключить сервер")
        btn_shutdown.setProperty("danger", True)
        
        top.addWidget(btn_refresh)
        top.addWidget(btn_logout)
        top.addWidget(btn_shutdown)
        v.addWidget(top_bar)
        
        tabs = QtWidgets.QTabWidget()
        tabs.setDocumentMode(False)
        tabs.setTabPosition(QtWidgets.QTabWidget.North)
        tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #555;
                border-radius: 4px;
                background-color: #252525;
                margin-top: 6px;
            }
            
            QTabBar::tab {
                background-color: #3c3c3c;
                color: #d4d4d4;
                padding: 12px 24px;
                margin-right: 2px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                border: 1px solid #555;
                border-bottom: none;
                font-size: 11pt;
                min-height: 40px;
                min-width: 120px;
            }
            
            QTabBar::tab:hover {
                background-color: #4a4a4a;
                border-color: #666;
            }
            
            QTabBar::tab:selected {
                background-color: #252525;
                color: white;
                font-weight: bold;
                border-bottom: 2px solid #0d6efd;
                padding-bottom: 10px;
            }
            
            QTabBar::tab:!selected {
                margin-top: 4px;
            }
            
            QTabBar {
                background-color: transparent;
            }
        """)
        
        # Agents tab
        t_agents = QtWidgets.QWidget()
        ta = QtWidgets.QVBoxLayout(t_agents)
        ta.setSpacing(10)
        
        header_agents = QtWidgets.QLabel("🖥️ Мониторинг подключенных компьютеров")
        header_agents.setStyleSheet("font-size: 11pt; color: #bbb; padding: 5px;")
        ta.addWidget(header_agents)
        
        self.table_agents = QtWidgets.QTableWidget(0, 6)
        self.table_agents.setHorizontalHeaderLabels(["🆔 HWID", "📛 Имя", "📍 IP", "⏰ Последний", "🔴 Статус", "⚙️ Действия"])
        self.table_agents.horizontalHeader().setStretchLastSection(False)
        self.table_agents.setColumnWidth(0, 180)
        self.table_agents.setColumnWidth(1, 120)
        self.table_agents.setColumnWidth(2, 120)
        self.table_agents.setColumnWidth(3, 150)
        self.table_agents.setColumnWidth(4, 100)
        self.table_agents.horizontalHeader().setSectionResizeMode(5, QtWidgets.QHeaderView.Stretch)
        self.table_agents.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table_agents.setAlternatingRowColors(True)
        ta.addWidget(self.table_agents, 1)
        
        tabs.addTab(t_agents, "🖥️ Мониторинг")
        
        # Tasks tab
        t_tasks = QtWidgets.QWidget()
        tt = QtWidgets.QVBoxLayout(t_tasks)
        tt.setSpacing(10)
        
        header_tasks = QtWidgets.QLabel("📋 Управление задачами")
        header_tasks.setStyleSheet("font-size: 11pt; color: #bbb; padding: 5px;")
        tt.addWidget(header_tasks)
        
        self.table_tasks = QtWidgets.QTableWidget(0, 5)
        self.table_tasks.setHorizontalHeaderLabels(["🆔 ID", "📝 Тип", "🎯 Цели", "📅 Создано", "⚙️ Действия"])
        self.table_tasks.horizontalHeader().setStretchLastSection(False)
        self.table_tasks.setColumnWidth(0, 100)
        self.table_tasks.setColumnWidth(1, 100)
        self.table_tasks.setColumnWidth(2, 250)
        self.table_tasks.setColumnWidth(3, 150)
        self.table_tasks.horizontalHeader().setSectionResizeMode(4, QtWidgets.QHeaderView.Stretch)
        self.table_tasks.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table_tasks.setAlternatingRowColors(True)
        tt.addWidget(self.table_tasks, 1)
        
        btn_new_task = QtWidgets.QPushButton("➕ Создать задачу")
        btn_new_task.setProperty("primary", True)
        tt.addWidget(btn_new_task)
        
        tabs.addTab(t_tasks, "📋 Задачи")
        
        # Approvals tab
        t_app = QtWidgets.QWidget()
        tap = QtWidgets.QVBoxLayout(t_app)
        tap.setSpacing(10)
        
        header_app = QtWidgets.QLabel("⏳ Ожидающие подтверждения")
        header_app.setStyleSheet("font-size: 11pt; color: #bbb; padding: 5px;")
        tap.addWidget(header_app)
        
        self.table_pending = QtWidgets.QTableWidget(0, 4)
        self.table_pending.setHorizontalHeaderLabels(["🆔 HWID", "📛 Имя", "📍 IP", "⚙️ Действия"])
        self.table_pending.horizontalHeader().setStretchLastSection(False)
        self.table_pending.setColumnWidth(0, 180)
        self.table_pending.setColumnWidth(1, 120)
        self.table_pending.setColumnWidth(2, 120)
        self.table_pending.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.Stretch)
        self.table_pending.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table_pending.setAlternatingRowColors(True)
        tap.addWidget(self.table_pending, 1)
        
        tabs.addTab(t_app, "⏳ Запросы")
        
        # Users tab
        t_users = QtWidgets.QWidget()
        tu = QtWidgets.QVBoxLayout(t_users)
        tu.setSpacing(10)
        
        header_users = QtWidgets.QLabel("👤 Управление пользователями")
        header_users.setStyleSheet("font-size: 11pt; color: #bbb; padding: 5px;")
        tu.addWidget(header_users)
        
        self.table_users = QtWidgets.QTableWidget(0, 3)
        self.table_users.setHorizontalHeaderLabels(["👤 Имя", "🔐 Привилегии", "⚙️ Действия"])
        self.table_users.horizontalHeader().setStretchLastSection(False)
        self.table_users.setColumnWidth(0, 150)
        self.table_users.setColumnWidth(1, 300)
        self.table_users.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        self.table_users.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table_users.setAlternatingRowColors(True)
        self.table_users.setObjectName("table_users")
        tu.addWidget(self.table_users, 1)
        
        btn_new_user = QtWidgets.QPushButton("➕ Создать пользователя")
        btn_new_user.setProperty("primary", True)
        tu.addWidget(btn_new_user)
        
        tabs.addTab(t_users, "👤 Пользователи")
        
        # Logs tab
        t_logs = QtWidgets.QWidget()
        tl = QtWidgets.QVBoxLayout(t_logs)
        tl.setSpacing(10)
        
        header_logs = QtWidgets.QLabel("📜 Просмотр логов системы")
        header_logs.setStyleSheet("font-size: 11pt; color: #bbb; padding: 5px;")
        tl.addWidget(header_logs)
        
        btn_logs = QtWidgets.QPushButton("📜 Просмотр логов")
        btn_logs.setProperty("primary", True)
        btn_logs.setMaximumWidth(200)
        tl.addWidget(btn_logs)
        tl.addStretch()
        
        tabs.addTab(t_logs, "📜 Логи")
        
        v.addWidget(tabs, 1)
        self.stack.addWidget(page)
        
        # Connect signals
        btn_add.clicked.connect(self.add_server)
        btn_edit.clicked.connect(self.edit_server)
        btn_del.clicked.connect(self.del_server)
        self.btn_connect.clicked.connect(self.connect_selected)
        btn_refresh.clicked.connect(self.fetch_state)
        btn_logout.clicked.connect(self.logout)
        btn_shutdown.clicked.connect(self.shutdown_server)
        btn_new_task.clicked.connect(self.create_task)
        btn_new_user.clicked.connect(self.create_user)
        btn_logs.clicked.connect(self.open_logs)
        
        self.populate_servers()
        self.stack.setCurrentIndex(0)
        self.setup_table_sorting()
    
    def setup_table_sorting(self):
        self.table_agents.setSortingEnabled(True)
        self.table_agents.horizontalHeader().setSectionsClickable(True)
        self.table_tasks.setSortingEnabled(True)
        self.table_tasks.horizontalHeader().setSectionsClickable(True)
        self.table_pending.setSortingEnabled(True)
        self.table_pending.horizontalHeader().setSectionsClickable(True)
        self.table_users.setSortingEnabled(True)
        self.table_users.horizontalHeader().setSectionsClickable(True)
    
    def populate_servers(self):
        self.list_servers.clear()
        for s in self.servers:
            proto = "🔒" if s.get("use_https") else "🌐"
            it = QtWidgets.QListWidgetItem(f"{proto} {s.get('name','')} — {s.get('host')}:{s.get('port')}")
            it.setData(QtCore.Qt.UserRole, s)
            self.list_servers.addItem(it)
    
    def add_server(self):
        d = ServerEditDialog(self)
        if d.exec_() == QtWidgets.QDialog.Accepted:
            s = d.get_data()
            self.servers.append(s)
            save_servers(self.servers)
            self.populate_servers()
    
    def edit_server(self):
        it = self.list_servers.currentItem()
        if not it:
            QtWidgets.QMessageBox.information(self, "⚠️ Ошибка", "Выберите сервер для редактирования")
            return
        s = it.data(QtCore.Qt.UserRole)
        d = ServerEditDialog(self, s)
        if d.exec_() == QtWidgets.QDialog.Accepted:
            new = d.get_data()
            idx = self.list_servers.currentRow()
            self.servers[idx] = new
            save_servers(self.servers)
            self.populate_servers()
    
    def del_server(self):
        it = self.list_servers.currentItem()
        if not it:
            return
        if QtWidgets.QMessageBox.question(
            self,
            "🗑️ Удаление",
            f"Удалить сервер '{it.text()}' из списка?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        ) != QtWidgets.QMessageBox.Yes:
            return
        idx = self.list_servers.currentRow()
        del self.servers[idx]
        save_servers(self.servers)
        self.populate_servers()
    
    def connect_selected(self):
        it = self.list_servers.currentItem()
        if not it:
            QtWidgets.QMessageBox.information(self, "⚠️ Ошибка", "Выберите сервер для подключения")
            return
        s = it.data(QtCore.Qt.UserRole)
        proto = "https" if s.get("use_https") else "http"
        base = f"{proto}://{s.get('host')}:{s.get('port')}"
        verify = s.get("verify_ssl", True)
        self.start_connect(base, verify)
    
    def start_connect(self, base, verify):
        self.lbl_status.setText("🔄 Подключение...")
        self.worker = ConnectWorker(base, verify, tries=10, delay=3)
        self.worker.progress.connect(lambda t: self.lbl_status.setText(t))
        self.worker.finished_ok.connect(lambda sess: self.connect_ok(base, sess))
        self.worker.finished_fail.connect(lambda r: self.lbl_status.setText(f"❌ Не удалось: {r}"))
        self.worker.start()
        
        dlg = QtWidgets.QMessageBox(self)
        dlg.setWindowTitle("🔗 Подключение")
        dlg.setText("Выполняется подключение к серверу...\n\nЗакройте это окно для отмены.")
        dlg.setStandardButtons(QtWidgets.QMessageBox.Close)
        dlg.setStyleSheet("QLabel{min-width: 300px;}")
        dlg.button(QtWidgets.QMessageBox.Close).clicked.connect(lambda: self.worker.stop())
        dlg.show()
    
    def update_clock(self):
        """Обновляет отображение часов"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.lbl_clock.setText(f"🕐 {current_time}")
    
    def connect_ok(self, base, session):
        self.current_base = base
        self.update_clock()
        
        # Показываем диалог входа
        login_dialog = LoginDialog(base, self)
        if login_dialog.exec_() == QtWidgets.QDialog.Accepted:
            self.auth_token = login_dialog.get_auth_token()
            self.lbl_status.setText("✅ Авторизация успешна")
            
            # Получаем информацию о пользователе
            try:
                headers = {"Authorization": f"Basic {self.auth_token}"}
                response = requests.get(
                    f"{base}/api/auth/verify",
                    headers=headers,
                    timeout=6,
                    verify=False
                )
                if response.status_code == 200:
                    data = response.json()
                    self.current_user = data.get("username")
                    self.fetch_state()
                    self.stack.setCurrentIndex(1)
                else:
                    self.lbl_status.setText("❌ Ошибка получения информации о пользователе")
            except Exception as e:
                self.lbl_status.setText(f"❌ Ошибка: {str(e)}")
        else:
            self.lbl_status.setText("❌ Авторизация отменена")
    
    def fetch_state(self):
        if not self.current_base or not self.auth_token:
            QtWidgets.QMessageBox.information(self, "Нет соединения", "Сначала подключитесь к серверу")
            return
        
        headers = {"Authorization": f"Basic {self.auth_token}"}
        
        try:
            # Получаем состояние сервера
            response = requests.get(
                f"{self.current_base}/api/state",
                headers=headers,
                timeout=8,
                verify=False
            )
            
            if response.status_code != 200:
                QtWidgets.QMessageBox.warning(self, "Ошибка", 
                    f"Не удалось получить состояние: {response.status_code}\n{response.text[:200]}")
                return
            
            st = response.json()
            
            # ДЛЯ ОТЛАДКИ - выводим статусы агентов
            print("\n=== ДЕБАГ ИНФОРМАЦИЯ ===")
            print(f"Всего агентов: {len(st.get('agents', {}))}")
            for agent_id, agent_info in st.get('agents', {}).items():
                print(f"Агент {agent_id}: статус={agent_info.get('status')}, last_seen={agent_info.get('last_seen')}, approved={agent_info.get('approved')}")
            print("=====================\n")
            
            self.lbl_srvdesc.setText(f"🌐 {st.get('server_desc','')} | 👤 {self.current_user}")
            self.populate_agents(st.get("agents", {}))
            self.populate_tasks(st.get("tasks", []))
            self.populate_pending(st.get("pending", {}))
            self.populate_users_api()
            
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Ошибка", str(e))
        
    def populate_agents(self, agents):
        print(f"DEBUG: populate_agents вызвана с {len(agents)} агентами")
        self.table_agents.setRowCount(0)
        self._agents_cache = agents or {}
        
        # Отключаем сортировку при обновлении
        was_sorting_enabled = self.table_agents.isSortingEnabled()
        if was_sorting_enabled:
            self.table_agents.setSortingEnabled(False)
        
        for aid in sorted(self._agents_cache.keys()):
            info = self._agents_cache[aid]
            r = self.table_agents.rowCount()
            self.table_agents.insertRow(r)
            
            print(f"DEBUG: Агент {aid}, данные: {info}")
            
            # HWID (сокращаем для отображения)
            hwid_display = aid[:12] + "..." if len(aid) > 12 else aid
            self.table_agents.setItem(r, 0, QtWidgets.QTableWidgetItem(hwid_display))
            self.table_agents.setItem(r, 0, QtWidgets.QTableWidgetItem(hwid_display))
            
            # Имя
            name = info.get("name", aid)
            self.table_agents.setItem(r, 1, QtWidgets.QTableWidgetItem(name))
            
            # IP адрес
            ip_address = info.get("ip", "N/A")
            if ip_address == "0.0.0.0" or not ip_address or ip_address == "":
                ip_address = "N/A"
            self.table_agents.setItem(r, 2, QtWidgets.QTableWidgetItem(ip_address))
            
            # Время последнего контакта (форматируем)
            last_seen = info.get("last_seen", "")
            if last_seen:
                try:
                    # Пытаемся красиво отформатировать время
                    if last_seen.endswith('Z'):
                        last_seen = last_seen[:-1] + '+00:00'
                    dt = datetime.fromisoformat(last_seen)
                    # Приводим к локальному времени
                    dt_local = dt.astimezone()
                    formatted_time = dt_local.strftime("%Y-%m-%d %H:%M:%S")
                    time_item = QtWidgets.QTableWidgetItem(formatted_time)
                except Exception as e:
                    print(f"DEBUG: Ошибка форматирования времени {last_seen}: {e}")
                    time_item = QtWidgets.QTableWidgetItem(last_seen)
            else:
                time_item = QtWidgets.QTableWidgetItem("Never")
            
            self.table_agents.setItem(r, 3, time_item)
            
            # СТАТУС - используем статус с сервера
            status_from_server = info.get("status", "UNKNOWN").upper()
            approved = info.get("approved", False)
            
            print(f"DEBUG: Статус агента {aid}: server_status={status_from_server}, approved={approved}")
            
            # Определяем статус для отображения
            if status_from_server == "ONLINE" and approved:
                status_text = "🟢 Online"
                status_color = "#198754"
            elif status_from_server == "OFFLINE":
                status_text = "🔴 Offline"
                status_color = "#dc3545"
            elif not approved:
                status_text = "🟡 Pending"
                status_color = "#ffc107"
            elif status_from_server == "BLOCKED":
                status_text = "🚫 Blocked"
                status_color = "#dc3545"
            elif status_from_server == "UNKNOWN":
                # Пытаемся вычислить локально
                last_seen_time = info.get("last_seen", "")
                if last_seen_time and is_online(last_seen_time):
                    status_text = "🟢 Online"
                    status_color = "#198754"
                else:
                    status_text = "🔴 Offline"
                    status_color = "#dc3545"
            else:
                status_text = f"⚪ {status_from_server}"
                status_color = "#6c757d"
            
            status_item = QtWidgets.QTableWidgetItem(status_text)
            status_item.setForeground(QtGui.QColor(status_color))
            # Сохраняем исходный статус для сортировки
            status_item.setData(QtCore.Qt.UserRole, status_from_server)
            self.table_agents.setItem(r, 4, status_item)
            
            # Кнопки действий
            w = QtWidgets.QWidget()
            hl = QtWidgets.QHBoxLayout(w)
            hl.setContentsMargins(5, 2, 5, 2)
            hl.setSpacing(3)
            
            btn_proc = QtWidgets.QPushButton("📋")
            btn_proc.setToolTip("Мониторинг процессов")
            btn_proc.setMaximumWidth(40)
            btn_proc.setEnabled(status_from_server == "ONLINE" and approved)
            
            btn_fs = QtWidgets.QPushButton("📂")
            btn_fs.setToolTip("Файловая система")
            btn_fs.setMaximumWidth(40)
            btn_fs.setEnabled(status_from_server == "ONLINE" and approved)
            
            btn_info = QtWidgets.QPushButton("ℹ️")
            btn_info.setToolTip("Информация")
            btn_info.setMaximumWidth(40)
            
            btn_ren = QtWidgets.QPushButton("✏️")
            btn_ren.setToolTip("Переименовать")
            btn_ren.setMaximumWidth(40)
            
            btn_del = QtWidgets.QPushButton("🗑️")
            btn_del.setToolTip("Удалить")
            btn_del.setMaximumWidth(40)
            btn_del.setProperty("danger", True)
            
            hl.addWidget(btn_proc)
            hl.addWidget(btn_fs)
            hl.addWidget(btn_info)
            hl.addWidget(btn_ren)
            hl.addWidget(btn_del)
            hl.addStretch()
            
            self.table_agents.setCellWidget(r, 5, w)
            self.table_agents.setRowHeight(r, 50)
            
            # Подключаем сигналы
            btn_proc.clicked.connect(lambda checked, a=aid: self.open_monitor(a, "PROCESSES", ""))
            btn_fs.clicked.connect(lambda checked, a=aid: self.open_monitor(a, "FS", "C:\\"))
            btn_info.clicked.connect(lambda checked, a=aid: self.show_agent_info(a))
            btn_ren.clicked.connect(lambda checked, a=aid, n=name: self.rename_agent(a, n))
            btn_del.clicked.connect(lambda checked, a=aid: self.delete_agent(a))
        
        # Восстанавливаем сортировку
        if was_sorting_enabled:
            self.table_agents.setSortingEnabled(True)
        
        # Обновляем отображение
        self.table_agents.resizeColumnsToContents()
        self.table_agents.horizontalHeader().setStretchLastSection(True)
        
        print("DEBUG: populate_agents завершена")
    
    def populate_tasks(self, tasks):
        self.table_tasks.setRowCount(0)
        for t in reversed(tasks):
            r = self.table_tasks.rowCount()
            self.table_tasks.insertRow(r)
            
            self.table_tasks.setItem(r, 0, QtWidgets.QTableWidgetItem(t.get("id", "")))
            self.table_tasks.setItem(r, 1, QtWidgets.QTableWidgetItem(t.get("task_type", "")))
            
            targets = ", ".join([f"{a}:{s}" for a, s in t.get("status", {}).items()])
            self.table_tasks.setItem(r, 2, QtWidgets.QTableWidgetItem(targets[:100]))
            self.table_tasks.setItem(r, 3, QtWidgets.QTableWidgetItem(t.get("created_at", "")))
            
            w = QtWidgets.QWidget()
            hl = QtWidgets.QHBoxLayout(w)
            hl.setContentsMargins(5, 2, 5, 2)
            hl.setSpacing(3)
            
            bdel = QtWidgets.QPushButton("🗑️")
            bdel.setToolTip("Удалить задачу")
            bdel.setMaximumWidth(40)
            bdel.setProperty("danger", True)
            
            bforce = QtWidgets.QPushButton("⏩ Force DONE")
            bforce.setToolTip("Принудительно завершить")
            bforce.setMaximumWidth(120)
            
            hl.addWidget(bdel)
            hl.addWidget(bforce)
            hl.addStretch()
            
            self.table_tasks.setCellWidget(r, 4, w)
            self.table_tasks.setRowHeight(r, 45)
            
            bdel.clicked.connect(partial(self.api_delete_task, t.get("id")))
            bforce.clicked.connect(partial(self.api_force_done, t.get("id")))
    
    def populate_pending(self, pending):
        self.table_pending.setRowCount(0)
        for aid, p in (pending or {}).items():
            r = self.table_pending.rowCount()
            self.table_pending.insertRow(r)
            
            self.table_pending.setItem(r, 0, QtWidgets.QTableWidgetItem(aid))
            self.table_pending.setItem(r, 1, QtWidgets.QTableWidgetItem(p.get("name", "")))
            self.table_pending.setItem(r, 2, QtWidgets.QTableWidgetItem(p.get("ip", "")))
            
            w = QtWidgets.QWidget()
            hl = QtWidgets.QHBoxLayout(w)
            hl.setContentsMargins(5, 2, 5, 2)
            hl.setSpacing(5)
            
            allow = QtWidgets.QPushButton("✅ Разрешить")
            allow.setToolTip("Разрешить подключение")
            allow.setProperty("success", True)
            allow.setMaximumWidth(100)
            
            block = QtWidgets.QPushButton("❌ Блокировать")
            block.setToolTip("Заблокировать агент")
            block.setProperty("danger", True)
            block.setMaximumWidth(100)
            
            hl.addWidget(allow)
            hl.addWidget(block)
            hl.addStretch()
            
            self.table_pending.setCellWidget(r, 3, w)
            self.table_pending.setRowHeight(r, 45)
            
            allow.clicked.connect(partial(self.approve_agent, aid, True))
            block.clicked.connect(partial(self.approve_agent, aid, False))
    
    def populate_users_api(self):
        headers = {"Authorization": f"Basic {self.auth_token}"}
        
        try:
            response = requests.get(
                f"{self.current_base}/api/users",
                headers=headers,
                timeout=8,
                verify=False
            )
            
            if response.status_code == 200:
                users = response.json()
                was_sorting_enabled = self.table_users.isSortingEnabled()
                self.table_users.setSortingEnabled(False)
                
                self.table_users.setRowCount(0)
                self._users_cache = users
                
                for username, info in users.items():
                    rnum = self.table_users.rowCount()
                    self.table_users.insertRow(rnum)
                    
                    name_item = QtWidgets.QTableWidgetItem(username)
                    name_item.setFlags(name_item.flags() ^ QtCore.Qt.ItemIsEditable)
                    self.table_users.setItem(rnum, 0, name_item)
                    
                    privileges = info.get("privileges", [])
                    if isinstance(privileges, list):
                        privileges_text = ", ".join(privileges)
                    else:
                        privileges_text = str(privileges)
                    
                    priv_item = QtWidgets.QTableWidgetItem(privileges_text)
                    priv_item.setFlags(priv_item.flags() ^ QtCore.Qt.ItemIsEditable)
                    self.table_users.setItem(rnum, 1, priv_item)
                    
                    w = QtWidgets.QWidget()
                    hl = QtWidgets.QHBoxLayout(w)
                    hl.setContentsMargins(3, 3, 3, 3)
                    hl.setSpacing(5)
                    
                    if username.lower() != "admin":
                        btn_edit = QtWidgets.QPushButton("✏️")
                        btn_edit.setToolTip("Редактировать")
                        btn_edit.setFixedSize(60, 30)
                        btn_edit.clicked.connect(lambda checked, u=username: self.edit_user(u))
                        
                        btn_del = QtWidgets.QPushButton("🗑️")
                        btn_del.setToolTip("Удалить")
                        btn_del.setFixedSize(60, 30)
                        btn_del.setProperty("danger", True)
                        btn_del.clicked.connect(lambda checked, u=username: self.delete_user(u))
                        
                        btn_blacklist = QtWidgets.QPushButton("🚫")
                        btn_blacklist.setToolTip("Черный список команд")
                        btn_blacklist.setFixedSize(60, 30)
                        btn_blacklist.clicked.connect(lambda checked, u=username: self.manage_blacklist(u))
                        
                        hl.addWidget(btn_edit)
                        hl.addWidget(btn_del)
                        hl.addWidget(btn_blacklist)
                        hl.addStretch()
                    else:
                        label = QtWidgets.QLabel("Системный администратор")
                        label.setStyleSheet("color: #888; font-style: italic;")
                        hl.addWidget(label)
                        hl.addStretch()
                    
                    self.table_users.setCellWidget(rnum, 2, w)
                    self.table_users.setRowHeight(rnum, 45)
                
                if was_sorting_enabled:
                    self.table_users.setSortingEnabled(True)
            else:
                QtWidgets.QMessageBox.warning(self, "Ошибка", 
                    f"Не удалось получить список пользователей: {response.status_code}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Ошибка", f"Ошибка: {str(e)}")
    
    def manage_blacklist(self, username):
        headers = {"Authorization": f"Basic {self.auth_token}"}
        
        try:
            response = requests.get(
                f"{self.current_base}/api/user/{username}/blacklist",
                headers=headers,
                timeout=8,
                verify=False
            )
            
            if response.status_code == 200:
                data = response.json()
                current_blacklist = data.get("blacklist", [])
                
                dlg = BlacklistDialog(
                    self.current_base,
                    self.auth_token,
                    username,
                    current_blacklist,
                    parent=self
                )
                dlg.exec_()
                
                self.populate_users_api()
            else:
                QtWidgets.QMessageBox.warning(self, "Ошибка", 
                    f"Не удалось получить черный список: {response.status_code}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Ошибка", f"Ошибка: {str(e)}")
    
    def create_user(self):
        headers = {"Authorization": f"Basic {self.auth_token}"}
        
        try:
            response = requests.get(
                f"{self.current_base}/api/privs",
                headers=headers,
                timeout=6,
                verify=False
            )
            
            if response.status_code == 200:
                data = response.json()
                all_privs = data.get("privs", [])
            else:
                all_privs = ["approve_agent","run_cmd","manage_users","push_file","pull_file",
                            "view_info","view_logs","shutdown_server","cancel_tasks"]
            
            d = UserEditDialog(self.current_base, self.auth_token, 
                            user=None, privileges=None, all_privs=all_privs, parent=self)
            if d.exec_() == QtWidgets.QDialog.Accepted:
                self.populate_users_api()
                
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Ошибка", f"Ошибка: {str(e)}")
    
    def edit_user(self, username):
        if not username or username.lower() == "admin":
            QtWidgets.QMessageBox.warning(self, "Ошибка", "Нельзя редактировать системного администратора")
            return
        
        user_info = self._users_cache.get(username, {})
        
        headers = {"Authorization": f"Basic {self.auth_token}"}
        
        try:
            response = requests.get(
                f"{self.current_base}/api/privs",
                headers=headers,
                timeout=6,
                verify=False
            )
            
            if response.status_code == 200:
                all_privs = response.json().get("privs", [])
            else:
                all_privs = ["approve_agent","run_cmd","manage_users","push_file","pull_file",
                            "view_info","view_logs","shutdown_server","cancel_tasks"]
            
            d = UserEditDialog(self.current_base, self.auth_token, 
                            user=username, 
                            privileges=user_info.get("privileges", []), 
                            all_privs=all_privs, 
                            parent=self)
            if d.exec_() == QtWidgets.QDialog.Accepted:
                self.populate_users_api()
                
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Ошибка", f"Ошибка: {str(e)}")
    
    def delete_user(self, username):
        if not username or username.lower() == "admin":
            QtWidgets.QMessageBox.warning(self, "Ошибка", "Нельзя удалить системного администратора")
            return
        
        reply = QtWidgets.QMessageBox.question(
            self,
            "Подтверждение удаления",
            f"Вы уверены, что хотите удалить пользователя '{username}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        
        if reply != QtWidgets.QMessageBox.Yes:
            return
        
        headers = {"Authorization": f"Basic {self.auth_token}"}
        
        try:
            response = requests.post(
                f"{self.current_base}/api/users/delete",
                json={"username": username},
                headers=headers,
                timeout=8,
                verify=False
            )
            
            if response.status_code == 200:
                QtWidgets.QMessageBox.information(self, "Успех", f"Пользователь '{username}' удалён")
                self.populate_users_api()
            else:
                error_msg = f"Не удалось удалить пользователя:\n"
                error_msg += f"Статус: {response.status_code}\n"
                error_msg += f"Ответ: {response.text[:200]}"
                QtWidgets.QMessageBox.warning(self, "Ошибка", error_msg)
                
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Ошибка", f"Ошибка при удалении: {str(e)}")
    
    def open_monitor(self, aid, typ, path):
        dlg = MonitorDialog(self.current_base, self.auth_token, aid, typ, 
                        path=path, parent=self)
        dlg.exec_()
        self.fetch_state()
    
    def show_agent_info(self, aid):
        dlg = AgentInfoDialog(self.current_base, self.auth_token, aid, parent=self)
        dlg.exec_()
    
    def rename_agent(self, aid, old):
        new, ok = QtWidgets.QInputDialog.getText(self, "✏️ Переименовать", 
                                               "Введите новое имя:", text=old)
        if not ok:
            return
        
        headers = {"Authorization": f"Basic {self.auth_token}"}
        
        try:
            response = requests.post(
                f"{self.current_base}/api/agents/rename",
                json={"agent_id": aid, "new_name": new},
                headers=headers,
                timeout=8,
                verify=False
            )
            
            if response.status_code == 200:
                QtWidgets.QMessageBox.information(self, "✅ Успех", "Агент переименован")
                self.fetch_state()
            else:
                QtWidgets.QMessageBox.warning(self, "⚠️ Ошибка", f"{response.status_code} {response.text}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "⚠️ Ошибка", str(e))
    
    def delete_agent(self, aid):
        if QtWidgets.QMessageBox.question(
            self,
            "🗑️ Удаление",
            f"Удалить агент '{aid}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        ) != QtWidgets.QMessageBox.Yes:
            return
        
        headers = {"Authorization": f"Basic {self.auth_token}"}
        
        try:
            response = requests.post(
                f"{self.current_base}/api/agents/delete",
                json={"agent_id": aid},
                headers=headers,
                timeout=8,
                verify=False
            )
            
            if response.status_code == 200:
                QtWidgets.QMessageBox.information(self, "✅ Успех", "Агент удалён")
                self.fetch_state()
            else:
                QtWidgets.QMessageBox.warning(self, "⚠️ Ошибка", f"{response.status_code} {response.text}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "⚠️ Ошибка", str(e))
    
    def api_delete_task(self, tid):
        if QtWidgets.QMessageBox.question(
            self,
            "🗑️ Удаление",
            f"Удалить задачу '{tid}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        ) != QtWidgets.QMessageBox.Yes:
            return
        
        headers = {"Authorization": f"Basic {self.auth_token}"}
        
        try:
            response = requests.post(
                f"{self.current_base}/api/tasks/delete",
                json={"task_id": tid},
                headers=headers,
                timeout=8,
                verify=False
            )
            
            if response.status_code == 200:
                self.fetch_state()
            else:
                QtWidgets.QMessageBox.warning(self, "⚠️ Ошибка", f"{response.status_code}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "⚠️ Ошибка", str(e))
    
    def api_force_done(self, tid):
        headers = {"Authorization": f"Basic {self.auth_token}"}
        
        try:
            response = requests.post(
                f"{self.current_base}/api/tasks/force_done",
                json={"task_id": tid},
                headers=headers,
                timeout=8,
                verify=False
            )
            
            if response.status_code == 200:
                self.fetch_state()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "⚠️ Ошибка", str(e))
    
    def approve_agent(self, aid, allow):
        headers = {"Authorization": f"Basic {self.auth_token}"}
        
        try:
            response = requests.post(
                f"{self.current_base}/api/agents/approve",
                json={
                    "agent_id": aid,
                    "action": "approve" if allow else "block"
                },
                headers=headers,
                timeout=8,
                verify=False
            )
            
            if response.status_code == 200:
                self.fetch_state()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "⚠️ Ошибка", str(e))
    
    def create_task(self):
        dlg = CreateTaskDialog(self.current_base, self.auth_token, 
                              self._agents_cache, parent=self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            self.fetch_state()
    
    def logout(self):
        self.current_base = None
        self.auth_token = None
        self.current_user = None
        self.stack.setCurrentIndex(0)
        self.lbl_status.setText("🚪 Вышли из системы")
    
    def shutdown_server(self):
        if QtWidgets.QMessageBox.question(
            self,
            "⏻ Выключение",
            "Вы действительно хотите немедленно завершить процесс сервера?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        ) != QtWidgets.QMessageBox.Yes:
            return
        
        headers = {"Authorization": f"Basic {self.auth_token}"}
        
        try:
            response = requests.post(
                f"{self.current_base}/api/system/shutdown",
                headers=headers,
                timeout=8,
                verify=False
            )
            
            QtWidgets.QMessageBox.information(self, "✅ Успех", "Команда выключения отправлена")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "⚠️ Ошибка", str(e))
    
    def open_logs(self):
        dlg = LogsDialog(self.current_base, self.auth_token, parent=self)
        dlg.exec_()

# ---------------- Server edit dialog ----------------
class ServerEditDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, data=None):
        super().__init__(parent)
        self.setWindowTitle("🌐 Сервер")
        self.resize(460, 240)
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        
        v = QtWidgets.QVBoxLayout(self)
        v.setSpacing(15)
        v.setContentsMargins(20, 20, 20, 20)
        
        title = QtWidgets.QLabel("➕ Добавление сервера" if not data else "✏️ Редактирование сервера")
        title.setProperty("title", True)
        v.addWidget(title)
        
        form = QtWidgets.QFormLayout()
        form.setSpacing(10)
        
        self.name = QtWidgets.QLineEdit()
        self.name.setPlaceholderText("Имя сервера")
        
        self.host = QtWidgets.QLineEdit()
        self.host.setPlaceholderText("example.com или 192.168.1.1")
        
        self.port = QtWidgets.QLineEdit()
        self.port.setPlaceholderText("80 или 443")
        self.port.setValidator(QtGui.QIntValidator(1, 65535))
        
        self.use_https = QtWidgets.QCheckBox("Использовать HTTPS (SSL/TLS)")
        self.verify_ssl = QtWidgets.QCheckBox("Проверять SSL сертификат")
        self.verify_ssl.setChecked(True)
        
        form.addRow("📛 Имя:", self.name)
        form.addRow("📍 Хост/IP:", self.host)
        form.addRow("🔢 Порт:", self.port)
        form.addRow("", self.use_https)
        form.addRow("", self.verify_ssl)
        
        v.addLayout(form, 1)
        
        h = QtWidgets.QHBoxLayout()
        h.setSpacing(10)
        h.addStretch()
        ok = QtWidgets.QPushButton("💾 Сохранить")
        ok.setProperty("primary", True)
        cancel = QtWidgets.QPushButton("❌ Отмена")
        h.addWidget(ok)
        h.addWidget(cancel)
        v.addLayout(h)
        
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        
        if data:
            self.name.setText(data.get("name", ""))
            self.host.setText(data.get("host", ""))
            self.port.setText(str(data.get("port", "")))
            self.use_https.setChecked(data.get("use_https", False))
            self.verify_ssl.setChecked(data.get("verify_ssl", True))

    def get_data(self):
        return {
            "name": self.name.text().strip() or self.host.text().strip(),
            "host": self.host.text().strip(),
            "port": int(self.port.text().strip() or 80),
            "use_https": bool(self.use_https.isChecked()),
            "verify_ssl": bool(self.verify_ssl.isChecked())
        }

# ---------------- main ----------------
def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('Fusion')
    
    try:
        app.setWindowIcon(QtGui.QIcon('icon.png'))
    except:
        pass
    
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()