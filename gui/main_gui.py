# ~/sgsim_project/gui/main_gui_pyside6.py

import sys
import os
import subprocess
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QGridLayout, QHBoxLayout,
    QGroupBox, QCheckBox, QLabel, QComboBox, QLineEdit,
    QPushButton, QTextEdit
)
from PySide6.QtCore import QThread, QObject, Signal, Slot, QMetaObject, Qt

# PySide6.QtGui から QIcon をインポート
from PySide6.QtGui import QIcon
# PySide6.QtWidgets から QStyle をインポート
from PySide6.QtWidgets import QStyle

# --- Worker Class for Running Simulation in a Separate Thread ---
class SimulationWorker(QObject):
    """
    Runs the simulation subprocess in a separate thread to keep the GUI responsive.
    Emits signals to communicate with the main GUI thread.
    """
    output_received = Signal(str)
    error_received = Signal(str)
    finished = Signal(int)

    def __init__(self, command):
        super().__init__()
        self.command = command
        self.process = None
        self._is_running = False

    @Slot()
    def run(self):
        """Starts the simulation process."""
        if self._is_running:
            return
        self._is_running = True
        try:
            self.process = subprocess.Popen(
                self.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )

            for line in iter(self.process.stdout.readline, ''):
                self.output_received.emit(line)

            for line in iter(self.process.stderr.readline, ''):
                self.error_received.emit(line)

            self.process.stdout.close()
            self.process.stderr.close()
            self.process.wait()

        except Exception as e:
            self.error_received.emit(f"Failed to start process: {e}\n")
        finally:
            self._is_running = False
            self.finished.emit(self.process.returncode if self.process else 1)

    @Slot()
    def stop(self):
        """
        Stops the running simulation process. This slot is executed in the worker thread.
        """
        if self.process and self.process.poll() is None:
            self.output_received.emit("\n--- Sending termination signal to simulation ---\n")
            # プロセスを終了させる。run()メソッド内のループが終了し、
            # 最終的にfinishedシグナルが発行される。
            self.process.terminate()


# --- Main GUI Class ---
class SGSimGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.simulation_thread = None
        self.simulation_worker = None
        
        self.init_ui()

    #レイアウト
    #上にsimulation setting
    #下にsimulation output display
    #def init_ui(self):
    #    # (このメソッドに変更はありません)
    #    self.setWindowTitle("Skip Graph Simulator GUI")
    #    self.showMaximized()
    #    main_layout = QVBoxLayout(self)
    #    self.create_settings_groupbox()
    #    self.create_control_buttons()
    #    self.create_results_display()
    #    main_layout.addWidget(self.settings_groupbox)
    #    main_layout.addLayout(self.control_layout)
    #    main_layout.addWidget(self.results_text)
    #    self.update_widget_states()

    #レイアウト
    #左にsimulation setting
    #右にsimulation output display
    def init_ui(self):
        self.setWindowTitle("Skip Graph Simulator GUI")
        self.resize(1200, 800)
        self.showMaximized()
        main_layout = QHBoxLayout(self)  # ← 横並びレイアウト（左：設定＋ボタン、右：出力）
    
        # 左側（設定 + ボタン）
        left_layout = QVBoxLayout()
        self.create_settings_groupbox()
        self.create_control_buttons()
        left_layout.addWidget(self.settings_groupbox)
        left_layout.addLayout(self.control_layout)
        left_layout.addStretch()  # 下に余白を持たせる
    
        # 右側（出力表示）
        self.create_results_display()
        self.results_text.setStyleSheet("background-color: #2b2b2b; color: white; font-family: Consolas;")
    
        # 左右を main_layout に追加
        main_layout.addLayout(left_layout, 3.5)
        main_layout.addWidget(self.results_text, 6.5)

    
        self.update_widget_states()


    def create_settings_groupbox(self):
        # (このメソッドに変更はありません)
        self.settings_groupbox = QGroupBox("Simulation Settings")
        settings_layout = QGridLayout()
        self.fast_join_checkbox = QCheckBox("Fast Join (--fast-join)")
        self.fast_join_checkbox.setChecked(True)
        self.exp_combo = QComboBox()
        self.exp_combo.addItems(["basic", "unicast", "unicast_vary_n"])
        self.exp_combo.setCurrentText("unicast")
        self.n_edit = QLineEdit("8")
        self.alpha_edit = QLineEdit("2")
        self.unicast_algo_combo = QComboBox()
        self.unicast_algo_combo.addItems(["greedy", "original"])
        self.seed_edit = QLineEdit()
        self.seed_edit.setPlaceholderText("Leave empty for random seed")
        self.interactive_checkbox = QCheckBox("Display Graphs in Window (--interactive)")
        self.interactive_checkbox.setChecked(True)
        self.output_topology_max_level_edit = QLineEdit("0")
        self.output_hop_graph_checkbox = QCheckBox("Output Hop Graph (--output-hop-graph)")
        self.diagonal_checkbox = QCheckBox("Draw Diagonal Lines on Hop Graph (--diagonal)")
        self.verbose_checkbox = QCheckBox("Verbose Output (--verbose)")
        row = 0
        settings_layout.addWidget(self.fast_join_checkbox, row, 0, 1, 2); row += 1
        settings_layout.addWidget(QLabel("Experiment Type (--exp):"), row, 0)
        settings_layout.addWidget(self.exp_combo, row, 1); row += 1
        settings_layout.addWidget(QLabel("Number of Nodes (-n):"), row, 0)
        settings_layout.addWidget(self.n_edit, row, 1); row += 1
        settings_layout.addWidget(QLabel("Membership Vector Base (--alpha):"), row, 0)
        settings_layout.addWidget(self.alpha_edit, row, 1); row += 1
        settings_layout.addWidget(QLabel("Unicast Algorithm (--unicast-algorithm):"), row, 0)
        settings_layout.addWidget(self.unicast_algo_combo, row, 1); row += 1
        settings_layout.addWidget(QLabel("Random Seed (--seed):"), row, 0)
        settings_layout.addWidget(self.seed_edit, row, 1); row += 1
        settings_layout.addWidget(self.interactive_checkbox, row, 0, 1, 2); row += 1
        settings_layout.addWidget(QLabel("Topology Max Level (--output-topology-max-level):"), row, 0)
        settings_layout.addWidget(self.output_topology_max_level_edit, row, 1); row += 1
        settings_layout.addWidget(self.output_hop_graph_checkbox, row, 0, 1, 2); row += 1
        settings_layout.addWidget(self.diagonal_checkbox, row, 0, 1, 2); row += 1
        settings_layout.addWidget(self.verbose_checkbox, row, 0, 1, 2)
        self.settings_groupbox.setLayout(settings_layout)
        self.exp_combo.currentTextChanged.connect(self.update_widget_states)
        self.output_hop_graph_checkbox.toggled.connect(self.update_widget_states)

    def create_control_buttons(self):
        # (このメソッドに変更はありません)
        self.control_layout = QHBoxLayout()
        self.start_button = QPushButton("Start Simulation")
        # 標準アイコンを取得
        start_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        self.start_button.setIcon(start_icon)
        self.stop_button = QPushButton("Stop Simulation")
        stop_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop)
        self.stop_button.setIcon(stop_icon)
        self.stop_button.setEnabled(False)
        self.control_layout.addStretch()
        self.control_layout.addWidget(self.start_button)
        self.control_layout.addWidget(self.stop_button)
        self.control_layout.addStretch()
        self.start_button.clicked.connect(self.start_simulation)
        self.stop_button.clicked.connect(self.stop_simulation)
        
    

    def create_results_display(self):
        # (このメソッドに変更はありません)
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.results_text.setPlaceholderText("Simulation output will be displayed here...")

    @Slot()
    def update_widget_states(self):
        # (このメソッドに変更はありません)
        exp_type = self.exp_combo.currentText()
        output_hop_graph_checked = self.output_hop_graph_checkbox.isChecked()
        is_unicast_exp = exp_type in ["unicast", "unicast_vary_n"]
        self.unicast_algo_combo.setEnabled(is_unicast_exp)
        if not is_unicast_exp: self.unicast_algo_combo.setCurrentText("greedy")
        is_basic_exp = exp_type == "basic"
        self.output_topology_max_level_edit.setEnabled(is_basic_exp)
        if not is_basic_exp: self.output_topology_max_level_edit.setText("0")
        is_unicast_exp_for_hop = exp_type == "unicast"
        self.output_hop_graph_checkbox.setEnabled(is_unicast_exp_for_hop)
        self.diagonal_checkbox.setEnabled(is_unicast_exp_for_hop and output_hop_graph_checked)
        if not is_unicast_exp_for_hop: self.output_hop_graph_checkbox.setChecked(False)
        if not (is_unicast_exp_for_hop and output_hop_graph_checked): self.diagonal_checkbox.setChecked(False)

    @Slot()
    def start_simulation(self):
        """Builds the command and starts the simulation in a new thread."""
        self.results_text.clear()
        self.results_text.append("Starting simulation...")
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

        # (引数構築のロジックに変更はありません)
        args_list = []
        if self.fast_join_checkbox.isChecked(): args_list.append("--fast-join")
        args_list.extend(["--exp", self.exp_combo.currentText()])
        args_list.extend(["-n", self.n_edit.text()])
        args_list.extend(["--alpha", self.alpha_edit.text()])
        if self.exp_combo.currentText() in ["unicast", "unicast_vary_n"]: args_list.extend(["--unicast-algorithm", self.unicast_algo_combo.currentText()])
        if self.seed_edit.text(): args_list.extend(["--seed", self.seed_edit.text()])
        if self.interactive_checkbox.isChecked(): args_list.append("--interactive")
        if self.exp_combo.currentText() == "basic" and int(self.output_topology_max_level_edit.text()) > 0: args_list.extend(["--output-topology-max-level", self.output_topology_max_level_edit.text()])
        if self.exp_combo.currentText() == "unicast" and self.output_hop_graph_checkbox.isChecked():
            args_list.append("--output-hop-graph")
            if self.diagonal_checkbox.isChecked(): args_list.append("--diagonal")
        if self.verbose_checkbox.isChecked(): args_list.append("--verbose")
        script_path = os.path.join(os.path.dirname(__file__), "..", "sgsim-py313", "src", "sg_main.py")
        command = [sys.executable, script_path] + args_list
        self.results_text.append(f"Execution command: {' '.join(command)}\n")

        # --- スレッドとワーカーのセットアップ ---
        self.simulation_thread = QThread()
        self.simulation_worker = SimulationWorker(command)
        self.simulation_worker.moveToThread(self.simulation_thread)

        # --- ★★★ 修正点1: シグナル接続の整理 ★★★
        # 処理の各段階で適切なスロットを呼び出すように接続を整理します。

        # 1. ワーカーからGUIへのデータ通知
        self.simulation_worker.output_received.connect(self.append_output)
        self.simulation_worker.error_received.connect(self.append_error)
        self.simulation_worker.finished.connect(self.on_process_finished)

        # 2. スレッドの開始と、ワーカーのタスク実行を連携
        self.simulation_thread.started.connect(self.simulation_worker.run)
        
        # 3. ワーカー終了後、スレッドを安全に終了させる
        self.simulation_worker.finished.connect(self.simulation_thread.quit)

        # 4. オブジェクトのメモリリークを防ぐためのクリーンアップ
        self.simulation_worker.finished.connect(self.simulation_worker.deleteLater)
        self.simulation_thread.finished.connect(self.simulation_thread.deleteLater)

        # 5. スレッドが「完全に」終了した後に、GUIの状態を安全に更新
        self.simulation_thread.finished.connect(self.on_thread_finished)
        
        self.simulation_thread.start()

    @Slot()
    def stop_simulation(self):
        """
        ★★★ 修正点2: GUIをブロックせずに安全に停止要求を送る ★★★
        """
        if self.simulation_worker and self.simulation_thread and self.simulation_thread.isRunning():
            # QMetaObjectを使って、stop()スロットの実行をワーカースレッドの
            # イベントキューに投入します。これによりGUIがフリーズしません。
            QMetaObject.invokeMethod(self.simulation_worker, "stop", Qt.ConnectionType.QueuedConnection)
            # Stopボタンは即座に無効化して、連打を防ぎます
            self.stop_button.setEnabled(False)
    
    @Slot()
    def stop_simulation(self):
        """
        ★★★ 修正点: GUIスレッドから直接サブプロセスを停止させる ★★★
        """
        # ワーカーと、その内部のプロセスが存在し、かつ実行中であることを確認
        if (self.simulation_worker and 
            hasattr(self.simulation_worker, 'process') and 
            self.simulation_worker.process and 
            self.simulation_worker.process.poll() is None):
            
            self.results_text.append("\n--- Sending termination signal to simulation ---\n")
            
            # GUIスレッドから直接、ワーカーが管理するプロセスを終了させる
            self.simulation_worker.process.terminate()
            
            # Stopボタンは即座に無効化して連打を防ぐ
            self.stop_button.setEnabled(False)
        else:
            # プロセスが既に存在しない場合などのフォールバック処理
            self.stop_button.setEnabled(False)
            if not (self.simulation_thread and self.simulation_thread.isRunning()):
                self.start_button.setEnabled(True)

    # ... (append_output, on_process_finished, on_thread_finished などのメソッドは変更なし) ...
    
    def closeEvent(self, event):
        """
        ウィンドウを閉じる際に、実行中のシミュレーションがあれば停止させます。
        (stop_simulationのロジック変更に伴い、こちらも修正)
        """
        if self.simulation_thread and self.simulation_thread.isRunning():
            # 修正されたstop_simulationを呼び出すだけで良い
            self.stop_simulation()
            # スレッドが終了するのを少し待つ
            if self.simulation_thread:
                self.simulation_thread.wait(1000) 
        super().closeEvent(event)

    @Slot(str)
    def append_output(self, text):
        self.results_text.setTextColor("white")
        self.results_text.insertPlainText(text)
        self.results_text.verticalScrollBar().setValue(self.results_text.verticalScrollBar().maximum())

    @Slot(str)
    def append_error(self, text):
        self.results_text.setTextColor("red")
        self.results_text.insertPlainText(f"ERROR: {text}")
        self.results_text.setTextColor("white")
        self.results_text.verticalScrollBar().setValue(self.results_text.verticalScrollBar().maximum())

    @Slot(int)
    def on_process_finished(self, exit_code):
        """
        ★★★ 修正点3: 新しいスロット(ワーカーの処理完了時に呼ばれる) ★★★
        シミュレーション「プロセス」が完了したときに呼ばれます。
        ここではメッセージを表示するだけにし、GUIの状態変更は行いません。
        """
        self.results_text.append(f"\nSimulation process finished with exit code: {exit_code}.\n")

    @Slot()
    def on_thread_finished(self):
        """
        ★★★ 修正点4: 新しいスロット(スレッドの完全終了時に呼ばれる) ★★★
        シミュレーション「スレッド」が完全に終了したときに呼ばれます。
        この時点であれば、GUIの状態を更新したり、オブジェクト参照をクリアしても安全です。
        """
        self.results_text.append("Simulation thread has been terminated.\n")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.simulation_thread = None
        self.simulation_worker = None
        
    def closeEvent(self, event):
        """ウィンドウを閉じる際に、実行中のシミュレーションがあれば停止させます。"""
        if self.simulation_thread and self.simulation_thread.isRunning():
            self.stop_simulation()
            # スレッドが終了するのを少し待つ
            self.simulation_thread.wait(1000) 
        super().closeEvent(event)


# qt_material をインポート
from qt_material import apply_stylesheet

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # スタイルシートを適用（ダークモードの青色テーマ）
    apply_stylesheet(app, theme='dark_blue.xml')

    window = SGSimGUI()
    window.show()
    sys.exit(app.exec())