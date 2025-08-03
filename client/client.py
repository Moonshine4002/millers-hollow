import sys

from PySide6 import QtCore, QtWidgets, QtGui
import httpx


class MainWidget(QtWidgets.QWidget):
    STYLE_SHEET = {
        'success': 'color: #00dd00;',
        'error': 'color: #dd0000;',
    }

    def __init__(self):
        super().__init__()
        self.player_id = 0
        self.room = 0

        SPACING = 10
        MINIMUM_WIDTH = 100

        # user
        self.user_input_name = QtWidgets.QLineEdit()
        self.user_input_name.setPlaceholderText('name')
        self.user_input_controller = QtWidgets.QLineEdit()
        self.user_input_controller.setPlaceholderText('controller')
        self.user_verification = QtWidgets.QPushButton('login/register')
        self.user_verification.clicked.connect(self.button_register)
        self.user_status = QtWidgets.QLabel('')

        self.user_input_room = QtWidgets.QLineEdit()
        self.user_input_room.setEnabled(False)
        self.user_button_join = QtWidgets.QPushButton('join')
        self.user_button_join.clicked.connect(self.button_join)
        self.user_button_join.setEnabled(False)
        self.user_button_create = QtWidgets.QPushButton('create')
        self.user_button_create.clicked.connect(self.button_create)
        self.user_button_create.setEnabled(False)
        self.user_button_start = QtWidgets.QPushButton('start')
        self.user_button_start.clicked.connect(self.button_start)
        self.user_button_start.setEnabled(False)
        self.user_game_status = QtWidgets.QLabel('')

        self.user_room = QtWidgets.QHBoxLayout()
        self.user_room.addWidget(self.user_button_join)
        self.user_room.addWidget(self.user_button_create)

        self.user_form = QtWidgets.QFormLayout()
        self.user_form.addRow(QtWidgets.QLabel('name: '), self.user_input_name)
        self.user_form.addRow(
            QtWidgets.QLabel('controller: '), self.user_input_controller
        )
        self.user_form.addRow(self.user_verification)
        self.user_form.addRow(self.user_status)
        self.user_form.addRow(QtWidgets.QLabel('room: '), self.user_input_room)
        self.user_form.addRow(self.user_room)
        self.user_form.addRow(self.user_button_start)
        self.user_form.addRow(self.user_game_status)

        self.user = QtWidgets.QGroupBox('user')
        self.user.setLayout(self.user_form)

        # player
        self.player_table = QtWidgets.QTableWidget()
        self.player_table.setRowCount(9)
        self.player_table.setColumnCount(3)
        self.player_table.setHorizontalHeaderLabels(['Name', 'Seat', 'Life'])
        self.player_button = QtWidgets.QPushButton('refresh')
        self.player_button.clicked.connect(self.button_stats_player)
        self.player_button.setEnabled(False)

        self.player_form = QtWidgets.QFormLayout()
        self.player_form.addRow(self.player_table)
        self.player_form.addRow(self.player_button)

        self.player = QtWidgets.QGroupBox('player')
        self.player.setLayout(self.player_form)

        self.l_layout = QtWidgets.QVBoxLayout()
        self.l_layout.addWidget(self.user)
        self.l_layout.addWidget(self.player)

        # log
        self.log_text = QtWidgets.QLabel('')
        self.log_button = QtWidgets.QPushButton('refresh')
        self.log_button.clicked.connect(self.button_stats_log)
        self.log_button.setEnabled(False)

        self.log_layout = QtWidgets.QVBoxLayout()
        self.log_layout.addWidget(self.log_text)
        self.log_layout.addWidget(self.log_button)

        self.log = QtWidgets.QGroupBox('log')
        self.log.setLayout(self.log_layout)

        # action
        self.question = QtWidgets.QLabel('question')
        self.answer = QtWidgets.QTextEdit('answer')

        self.action_layout = QtWidgets.QVBoxLayout()
        self.action_layout.addWidget(self.question)
        self.action_layout.addWidget(self.answer)

        self.action = QtWidgets.QGroupBox('action')
        self.action.setLayout(self.action_layout)

        self.r_layout = QtWidgets.QVBoxLayout()
        self.r_layout.addWidget(self.log)
        self.r_layout.addWidget(self.action)

        self.h_layout = QtWidgets.QHBoxLayout(self)
        self.h_layout.addLayout(self.l_layout)
        self.h_layout.addLayout(self.r_layout)

    @QtCore.Slot()
    def button_login(self) -> None:
        self.user_verification.setEnabled(False)
        self.user_input_name.setEnabled(False)
        self.user_input_controller.setEnabled(False)
        self.user_name = self.user_input_name.text()
        self.user_controller = self.user_input_controller.text()
        data = {'name': self.user_name, 'controller': self.user_controller}
        try:
            response = httpx.post(
                'http://localhost:8000/login', json=data, follow_redirects=True
            )
            response.raise_for_status()
            success = True
            self.player_id = response.json()['id']
            text = response.json()['message']
        except httpx.HTTPStatusError as e:
            success = False
            text = response.json()['message']
        except Exception as e:
            success = False
            text = f'Error: {e}'
        if success:
            sytle_sheet_key = 'success'
            self.user_input_room.setEnabled(True)
            self.user_button_join.setEnabled(True)
            self.user_button_create.setEnabled(True)
        else:
            sytle_sheet_key = 'error'
            self.user_verification.setEnabled(True)
            self.user_input_name.setEnabled(True)
            self.user_input_controller.setEnabled(True)
        self.user_status.setStyleSheet(self.STYLE_SHEET[sytle_sheet_key])
        self.user_status.setText(text)

    @QtCore.Slot()
    def button_register(self) -> None:
        self.button_login()

    @QtCore.Slot()
    def button_join(self) -> None:
        self.user_input_room.setEnabled(False)
        self.user_button_join.setEnabled(False)
        self.user_button_create.setEnabled(False)
        try:
            self.room = int(self.user_input_room.text())
            if self.room < 1:
                raise ValueError('Wrong room number')
            response = httpx.post(
                f'http://localhost:8000/games/{self.room}/players/{self.player_id}'
            )
            response.raise_for_status()
            success = True
            text = response.json()
        except httpx.HTTPStatusError as e:
            success = False
            text = response.json()
        except Exception as e:
            success = False
            text = f'Error: {e}'
        if success:
            sytle_sheet_key = 'success'
            self.player_button.setEnabled(True)
        else:
            sytle_sheet_key = 'error'
            self.user_input_room.setEnabled(True)
            self.user_button_join.setEnabled(True)
            self.user_button_create.setEnabled(True)
        self.user_game_status.setStyleSheet(self.STYLE_SHEET[sytle_sheet_key])
        self.user_game_status.setText(text)

    @QtCore.Slot()
    def button_create(self) -> None:
        self.user_input_room.setEnabled(False)
        self.user_button_join.setEnabled(False)
        self.user_button_create.setEnabled(False)
        try:
            response = httpx.post(f'http://localhost:8000/games')
            response.raise_for_status()
            self.room = response.json()['game_id']
            success = True
            text = 'success'
        except httpx.HTTPStatusError as e:
            success = False
            text = response.json()['message']
        except Exception as e:
            success = False
            text = f'Error: {e}'
        if success:
            sytle_sheet_key = 'success'
            self.user_input_room.setText(str(self.room))
            self.user_button_start.setEnabled(True)
        else:
            sytle_sheet_key = 'error'
            self.user_input_room.setEnabled(True)
            self.user_button_join.setEnabled(True)
            self.user_button_create.setEnabled(True)
        self.user_game_status.setStyleSheet(self.STYLE_SHEET[sytle_sheet_key])
        self.user_game_status.setText(text)
        if success:
            self.button_join()

    @QtCore.Slot()
    def button_start(self) -> None:
        self.user_button_start.setEnabled(False)
        try:
            self.room = int(self.user_input_room.text())
            if self.room < 1:
                raise ValueError('Wrong room number')
            response = httpx.post(
                f'http://localhost:8000/games/{self.room}/start'
            )
            response.raise_for_status()
            success = True
            text = response.json()
        except httpx.HTTPStatusError as e:
            success = False
            text = response.json()
        except Exception as e:
            success = False
            text = f'Error: {e}'
        if success:
            sytle_sheet_key = 'success'
            self.log_button.setEnabled(True)
        else:
            sytle_sheet_key = 'error'
            self.user_button_start.setEnabled(True)
        self.user_game_status.setStyleSheet(self.STYLE_SHEET[sytle_sheet_key])
        self.user_game_status.setText(text)

    @QtCore.Slot()
    def button_stats_player(self) -> None:
        self.player_button.setEnabled(False)
        try:
            response = httpx.get(
                f'http://localhost:8000/games/{self.room}/stats/player'
            )
            response.raise_for_status()
            for name, seat, life in response.json()['stats']:
                item_name = QtWidgets.QTableWidgetItem(name)
                item_seat = QtWidgets.QTableWidgetItem(str(seat))
                item_life = QtWidgets.QTableWidgetItem(str(life))
                self.player_table.setItem(seat - 1, 0, item_name)
                self.player_table.setItem(seat - 1, 1, item_seat)
                self.player_table.setItem(seat - 1, 2, item_life)
        except httpx.HTTPStatusError as e:
            print(response.json())
        except Exception as e:
            print(f'Error: {e}')
        self.player_button.setEnabled(True)

    @QtCore.Slot()
    def button_stats_log(self) -> None:
        self.log_button.setEnabled(False)
        try:
            response = httpx.get(
                f'http://localhost:8000/games/{self.room}/stats/log/players/{self.player_id}'
            )
            response.raise_for_status()
            self.log_text.setText(response.json()['stats'])
        except httpx.HTTPStatusError as e:
            print(response.json())
        except Exception as e:
            print(f'Error: {e}')
        self.log_button.setEnabled(True)

    def hd_refresh(self) -> None:
        if self.player_button.isEnabled():
            self.button_stats_player()
        if self.log_button.isEnabled():
            self.button_stats_log()


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, widget: MainWidget):
        super().__init__()
        self.setWindowTitle("Miller's Hollow")

        # Menu
        self.menu = self.menuBar()
        self.file_menu = self.menu.addMenu('File')
        self.status_menu = self.menu.addMenu('Status')

        # Exit
        exit_action = self.file_menu.addAction('Exit', self.close)
        exit_action.setShortcut('Ctrl+Q')

        # Refresh
        refresh_action = self.status_menu.addAction('Refresh', self.hd_refresh)
        refresh_action.setShortcut('Ctrl+R')

        # Status Bar
        self.status = self.statusBar()
        self.status.showMessage('Status Bar')

        # Widget
        self.main_widget = widget
        self.setCentralWidget(widget)

    def hd_refresh(self) -> None:
        self.main_widget.hd_refresh()


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    widget = MainWidget()
    window = MainWindow(widget)
    window.resize(800, 600)
    window.show()
    sys.exit(app.exec())
