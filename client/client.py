import sys
from typing import cast

from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QApplication,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
import httpx

ORIGIN = 'http://localhost:8000'


class MainWidget(QWidget):
    STYLE_SHEET = {
        'info': 'color: #000000;',
        'success': 'color: #00dd00;',
        'error': 'color: #dd0000;',
    }

    def __init__(self, window: 'MainWindow'):
        super().__init__()

        MINIMUM_WIDTH = 100
        MINIMUM_HEIGHT = 100
        SPACING = 10

        self.user_name = ''
        self.user_controller = ''
        self.user_id = 0
        self.seat = 0
        self.room = 0   # game_id
        self.started = False

        # window
        window.setCentralWidget(self)
        self.window_init()

        # user
        self.user_input_name = QLineEdit()
        self.user_input_name.setPlaceholderText('name')
        self.user_input_ctrl = QLineEdit()
        self.user_input_ctrl.setPlaceholderText('controller')
        self.user_verification = QPushButton('login/register')
        self.user_verification.clicked.connect(self.button_register)

        self.user_input_room = QLineEdit()
        self.user_input_room.setEnabled(False)
        self.user_join = QPushButton('join')
        self.user_join.clicked.connect(self.button_join)
        self.user_join.setEnabled(False)
        self.user_create = QPushButton('create')
        self.user_create.clicked.connect(self.button_create)
        self.user_create.setEnabled(False)
        self.user_start = QPushButton('start')
        self.user_start.clicked.connect(self.button_start)
        self.user_start.setEnabled(False)

        self.user_room = QHBoxLayout()
        self.user_room.addWidget(self.user_join)
        self.user_room.addWidget(self.user_create)

        self.user_form = QFormLayout()
        self.user_form.addRow(QLabel('name: '), self.user_input_name)
        self.user_form.addRow(QLabel('controller: '), self.user_input_ctrl)
        self.user_form.addRow(self.user_verification)
        self.user_form.addRow(QLabel('room: '), self.user_input_room)
        self.user_form.addRow(self.user_room)
        self.user_form.addRow(self.user_start)

        self.user = QGroupBox('user')
        self.user.setLayout(self.user_form)

        # player
        self.player_table = QTableWidget()
        self.player_refresh = QPushButton('refresh')
        self.player_refresh.clicked.connect(self.button_stats_player)
        self.player_refresh.setEnabled(False)

        self.player_form = QFormLayout()
        self.player_form.addRow(self.player_table)
        self.player_form.addRow(self.player_refresh)

        self.player = QGroupBox('player')
        self.player.setLayout(self.player_form)

        self.left_box = QVBoxLayout()
        self.left_box.addWidget(self.user)
        self.left_box.addWidget(self.player)

        # log
        self.log_text = QPlainTextEdit('')
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumSize(MINIMUM_WIDTH * 4, MINIMUM_HEIGHT * 2)
        self.log_refresh = QPushButton('refresh')
        self.log_refresh.clicked.connect(self.button_stats_log)
        self.log_refresh.setEnabled(False)

        self.log_box = QVBoxLayout()
        self.log_box.addWidget(self.log_text)
        self.log_box.addWidget(self.log_refresh)

        self.log = QGroupBox('log')
        self.log.setLayout(self.log_box)

        # action
        self.action_status = QPlainTextEdit('Please wait...')
        self.action_status.setReadOnly(True)
        self.action_status.setMinimumSize(MINIMUM_WIDTH * 4, MINIMUM_HEIGHT * 1)
        self.action_refresh = QPushButton('refresh')
        self.action_refresh.clicked.connect(self.button_stats_action)
        self.action_refresh.setEnabled(False)
        self.action_skill = QLineEdit('')
        self.action_skill.setPlaceholderText('skill')
        self.action_target = QLineEdit('')
        self.action_target.setPlaceholderText('target')
        self.action_speech = QTextEdit('')
        self.action_speech.setPlaceholderText('speech')
        self.action_reason = QTextEdit('')
        self.action_reason.setPlaceholderText('reason')
        self.action_send = QPushButton('send')
        self.action_send.clicked.connect(self.button_send)
        self.action_send.setEnabled(False)

        self.action_box = QVBoxLayout()
        self.action_box.addWidget(self.action_status)
        self.action_box.addWidget(self.action_refresh)
        self.action_box.addWidget(self.action_skill)
        self.action_box.addWidget(self.action_target)
        self.action_box.addWidget(self.action_speech)
        self.action_box.addWidget(self.action_reason)
        self.action_box.addWidget(self.action_send)

        self.action = QGroupBox('action')
        self.action.setLayout(self.action_box)

        self.right_box = QVBoxLayout()
        self.right_box.addWidget(self.log)
        self.right_box.addWidget(self.action)

        self.main_box = QHBoxLayout(self)
        self.main_box.addLayout(self.left_box)
        self.main_box.addLayout(self.right_box)

    def window_init(self) -> None:
        # Refresh
        self.status_menu = self.window().status_menu
        refresh_action = self.status_menu.addAction('New Game', self.hd_new)
        refresh_action.setShortcut('Ctrl+N')
        refresh_action = self.status_menu.addAction('Refresh', self.hd_refresh)
        refresh_action.setShortcut('Ctrl+R')

        # Status message
        self.status = self.window().status_message

    def window(self) -> 'MainWindow':
        return cast(MainWindow, super().window())

    def post(self, path: str, json: dict | None = None) -> httpx.Response:
        try:
            response = httpx.post(f'{ORIGIN}{path}', json=json)
        except Exception as e:
            response = httpx.Response(
                status_code=500,
                json={'detail': str(e)},
                request=httpx.Request('POST', f'{ORIGIN}{path}', json=json),
            )
        return response

    def get(self, path: str) -> httpx.Response:
        try:
            response = httpx.get(f'{ORIGIN}{path}')
        except Exception as e:
            response = httpx.Response(
                status_code=500,
                json={'detail': str(e)},
                request=httpx.Request('GET', f'{ORIGIN}{path}'),
            )
        return response

    @Slot()
    def button_login(self) -> None:
        self.user_verification.setEnabled(False)
        self.user_input_name.setEnabled(False)
        self.user_input_ctrl.setEnabled(False)

        self.user_name = self.user_input_name.text()
        self.user_controller = self.user_input_ctrl.text()
        data = {'name': self.user_name, 'controller': self.user_controller}
        try:
            response = self.post('/login', data)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            self.status_message(response.json()['detail'], 'error')
            self.user_verification.setEnabled(True)
            self.user_input_name.setEnabled(True)
            self.user_input_ctrl.setEnabled(True)
        except Exception as e:
            self.status_message(str(e), 'error')
        else:
            self.status_message(response.json()['message'], 'success')
            self.user_id = response.json()['id']
            self.user_input_room.setEnabled(True)
            self.user_join.setEnabled(True)
            self.user_create.setEnabled(True)

    @Slot()
    def button_register(self) -> None:
        self.button_login()

    @Slot()
    def button_create(self) -> None:
        self.user_input_room.setEnabled(False)
        self.user_join.setEnabled(False)
        self.user_create.setEnabled(False)
        try:
            response = self.post(f'/games')
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            self.status_message(response.json()['detail'], 'error')
            self.user_input_room.setEnabled(True)
            self.user_join.setEnabled(True)
            self.user_create.setEnabled(True)
        except Exception as e:
            self.status_message(str(e), 'error')
        else:
            self.status_message(response.json()['message'], 'success')
            self.room = response.json()['game_id']
            self.user_input_room.setText(str(self.room))
            self.button_join()
            self.user_start.setEnabled(True)

    @Slot()
    def button_join(self) -> None:
        self.user_input_room.setEnabled(False)
        self.user_join.setEnabled(False)
        self.user_create.setEnabled(False)
        try:
            self.room = int(self.user_input_room.text())
            if self.room < 1:
                raise ValueError('Wrong room number')
            response = self.post(f'/games/{self.room}/users/{self.user_id}')
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            self.status_message(response.json()['detail'], 'error')
            self.user_input_room.setEnabled(True)
            self.user_join.setEnabled(True)
            self.user_create.setEnabled(True)
        except Exception as e:
            self.status_message(str(e), 'error')
        else:
            self.status_message(response.json(), 'success')
            self.player_refresh.setEnabled(True)

    @Slot()
    def button_start(self) -> None:
        self.user_start.setEnabled(False)
        try:
            response = self.post(f'/games/{self.room}/users/{self.user_id}/start')
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            self.status_message(response.json()['detail'], 'error')
            self.user_start.setEnabled(True)
        except Exception as e:
            self.status_message(str(e), 'error')
        else:
            self.status_message(response.json()['message'], 'success')
            self.started = True
            self.seat = response.json()['seat']
            self.log_refresh.setEnabled(True)
            self.action_refresh.setEnabled(True)
            self.action_send.setEnabled(True)

    @Slot()
    def button_stats_player(self) -> None:
        self.player_refresh.setEnabled(False)
        try:
            response = self.get(f'/games/{self.room}/seats/{self.seat}/stats/player')
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            self.status_message(response.json()['detail'], 'error')
        except Exception as e:
            self.status_message(str(e), 'error')
        else:
            self.status_message(response.json()['message'], 'success')
            stats: dict[int, list] = response.json()['stats']
            self.player_table.setRowCount(len(stats))
            self.player_table.setColumnCount(4)
            self.player_table.setHorizontalHeaderLabels(['Name', 'Role', 'Faction', 'Life'])
            for seat_str, (name, *others, role, faction, life) in stats.items():
                seat = int(seat_str) - 1
                item_name = QTableWidgetItem(name)
                item_role = QTableWidgetItem(role)
                item_faction = QTableWidgetItem(faction)
                item_life = QTableWidgetItem(str(life))
                self.player_table.setItem(seat, 0, item_name)
                self.player_table.setItem(seat, 1, item_role)
                self.player_table.setItem(seat, 2, item_faction)
                self.player_table.setItem(seat, 3, item_life)
        self.player_refresh.setEnabled(True)

    @Slot()
    def button_stats_log(self) -> None:
        self.log_refresh.setEnabled(False)
        try:
            response = self.get(f'/games/{self.room}/seats/{self.seat}/stats/log')
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            self.status_message(response.json()['detail'], 'error')
        except Exception as e:
            self.status_message(str(e), 'error')
        else:
            self.status_message(response.json()['message'], 'success')
            self.log_text.setPlainText(response.json()['stats'])
        self.log_refresh.setEnabled(True)

    @Slot()
    def button_stats_action(self) -> None:
        self.action_refresh.setEnabled(False)
        try:
            response = self.get(f'/games/{self.room}/seats/{self.seat}/stats/action')
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            self.status_message(response.json()['detail'], 'error')
            self.action_status.setPlainText('Please wait...')
        except Exception as e:
            self.status_message(str(e), 'error')
            self.action_status.setPlainText('Please wait...')
        else:
            self.status_message(response.json()['message'], 'success')
            self.action_status.setPlainText(response.json()['stats'])
        self.action_refresh.setEnabled(True)

    @Slot()
    def button_send(self) -> None:
        self.action_send.setEnabled(False)
        try:
            data = {
                'skill': self.action_skill.text(),
                'target': int(self.action_target.text()),
                'speech': self.action_speech.toPlainText(),
                'reason': self.action_reason.toPlainText(),
            }
            response = self.post(
                f'/games/{self.room}/seats/{self.seat}/stats/action',
                data,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            self.status_message(response.json()['detail'], 'error')
        except Exception as e:
            self.status_message(str(e), 'error')
        else:
            self.status_message(response.json(), 'success')
        self.action_send.setEnabled(True)

    def status_message(self, message: str, style: str = 'info') -> None:
        self.status.setStyleSheet(self.STYLE_SHEET[style])
        self.status.setText(message)

    def hd_new(self) -> None:
        if not self.started:
            return
        self.user_input_room.setEnabled(True)
        self.user_join.setEnabled(True)
        self.user_create.setEnabled(True)
        self.user_start.setEnabled(False)
        self.player_refresh.setEnabled(False)
        self.log_refresh.setEnabled(False)
        self.action_refresh.setEnabled(False)
        self.action_send.setEnabled(False)

    def hd_refresh(self) -> None:
        if self.player_refresh.isEnabled() and not self.started:
            if not self.started:
                response = self.get(f'/games/{self.room}/users/{self.user_id}/start')
                self.seat = response.json()
                if self.seat:
                    self.started = True
                    self.log_refresh.setEnabled(True)
                    self.action_refresh.setEnabled(True)
                    self.action_send.setEnabled(True)
        if self.player_refresh.isEnabled():
            self.button_stats_player()
        if self.log_refresh.isEnabled():
            self.button_stats_log()
        if self.action_refresh.isEnabled():
            self.button_stats_action()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Title
        self.setWindowTitle("Miller's Hollow")

        # Menu
        self.menu = self.menuBar()
        self.file_menu = self.menu.addMenu('File')
        self.status_menu = self.menu.addMenu('Status')

        # File
        exit_action = self.file_menu.addAction('Exit', self.close)
        exit_action.setShortcut('Ctrl+Q')

        # Status Bar
        self.status = self.statusBar()
        self.status.showMessage('Status Bar')
        self.status_message = QLabel('')
        self.status.addPermanentWidget(self.status_message)

        # Widget
        self.main_widget = MainWidget(self)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(800, 600)
    window.show()
    sys.exit(app.exec())
