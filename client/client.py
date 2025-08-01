import httpx
import sys
from PySide6 import QtCore, QtWidgets, QtGui


class MainWidget(QtWidgets.QWidget):
    STYLE_SHEET = {
        'success': 'color: #00dd00;',
        'error': 'color: #dd0000;',
    }

    def __init__(self):
        super().__init__()

        SPACING = 10
        MINIMUM_WIDTH = 100

        self.user_input_name = QtWidgets.QLineEdit()
        self.user_input_name.setPlaceholderText('name')

        self.user_input_controller = QtWidgets.QLineEdit()
        self.user_input_controller.setPlaceholderText('controller')

        self.user_button = QtWidgets.QPushButton('login/register')
        self.user_button.clicked.connect(self.register)

        self.user_response = QtWidgets.QLabel('')

        self.user_form = QtWidgets.QFormLayout()
        self.user_form.addRow(QtWidgets.QLabel('name: '), self.user_input_name)
        self.user_form.addRow(
            QtWidgets.QLabel('controller: '), self.user_input_controller
        )
        self.user_form.addRow(self.user_button)
        self.user_form.addRow(self.user_response)

        self.user = QtWidgets.QGroupBox('user')
        self.user.setLayout(self.user_form)

        self.player_form = QtWidgets.QFormLayout()

        self.player = QtWidgets.QGroupBox('player')
        self.player.setLayout(self.player_form)

        self.l_layout = QtWidgets.QVBoxLayout()
        self.l_layout.addWidget(self.user)
        self.l_layout.addWidget(self.player)

        self.question = QtWidgets.QLabel('question')
        self.answer = QtWidgets.QTextEdit('answer')

        self.game_layout = QtWidgets.QVBoxLayout()
        self.game_layout.addWidget(self.question)
        self.game_layout.addWidget(self.answer)

        self.game = QtWidgets.QGroupBox('game')
        self.game.setLayout(self.game_layout)

        self.r_layout = QtWidgets.QVBoxLayout()
        self.r_layout.addWidget(self.game)

        self.h_layout = QtWidgets.QHBoxLayout(self)
        self.h_layout.addLayout(self.l_layout)
        self.h_layout.addLayout(self.r_layout)

    def register(self) -> None:
        self.user_button.setEnabled(False)
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
            text = response.json()
        except httpx.HTTPStatusError as e:
            success = False
            text = response.json()
        except Exception as e:
            success = False
            text = f'Error: {e}'
        if success:
            sytle_sheet_key = 'success'
        else:
            sytle_sheet_key = 'error'
            self.user_button.setEnabled(True)
            self.user_input_name.setEnabled(True)
            self.user_input_controller.setEnabled(True)
        self.user_response.setStyleSheet(self.STYLE_SHEET[sytle_sheet_key])
        self.user_response.setText(text)

    def login(self) -> None:
        self.register()


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, widget: QtWidgets.QWidget):
        super().__init__()
        self.setWindowTitle("Miller's Hollow")

        # Menu
        self.menu = self.menuBar()
        self.file_menu = self.menu.addMenu('File')

        # Exit
        exit_action = self.file_menu.addAction('Exit', self.close)
        exit_action.setShortcut('Ctrl+Q')

        # Status Bar
        self.status = self.statusBar()
        self.status.showMessage('Status Bar')

        # Widget
        self.setCentralWidget(widget)


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    widget = MainWidget()
    window = MainWindow(widget)
    window.resize(800, 600)
    window.show()
    sys.exit(app.exec())
