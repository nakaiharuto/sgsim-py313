# ~/sgsim_project/gui/main_gui.py

import tkinter as tk
from tkinter import ttk  # Provides more modern (themed) widgets
from tkinter import messagebox  # For displaying message boxes
import subprocess  # To execute external processes (sg_main.py)
import sys  # To get the path of the current Python interpreter via sys.executable
import os  # For file path operations
import threading  # To run the simulation without freezing the GUI
import queue  # For inter-thread communication


class SGSimGUI:
    def __init__(self, master):
        self.master = master  # The Tkinter root window
        master.title("Skip Graph Simulator GUI")  # Set the window title
        #master.geometry("800x700")  # Set the initial window size (width x height)
        # 追加: ウィンドウを画面最大化する
        master.attributes('-zoomed', True)

        # 最大化後もユーザーがリサイズできるようにする（デフォルトではTrueなので、明示的に設定する必要はないが念のため）
        master.resizable(True, True) # 幅方向も高さ方向もリサイズ可能にする

        # Variables to hold widget values
        self.fast_join_var = tk.BooleanVar(value=True)  # --fast-join
        self.exp_var = tk.StringVar(value="unicast")  # --exp
        self.n_var = tk.IntVar(value=8)  # -n
        self.alpha_var = tk.IntVar(value=2)  # --alpha
        self.unicast_algo_var = tk.StringVar(value="greedy")  # --unicast-algorithm
        self.seed_var = tk.StringVar(value="")  # --seed (string, treated as None if empty)
        self.interactive_var = tk.BooleanVar(value=True)  # --interactive
        self.output_topology_max_level_var = tk.IntVar(value=0)  # --output-topology-max-level
        self.output_hop_graph_var = tk.BooleanVar(value=False)  # --output-hop-graph
        self.diagonal_var = tk.BooleanVar(value=False)  # --diagonal
        self.verbose_var = tk.BooleanVar(value=False)  # -v / --verbose

        # Create and place widgets
        self.create_widgets()

        # Queue to reflect output from the thread to the GUI
        self.output_queue = queue.Queue()
        self.master.after(100, self.process_queue)  # Check the queue every 100ms

        # シミュレーションプロセスを保持する変数 (GUIから停止するために必要)
        self.simulation_process = None # 追加: 現在実行中のsubprocessプロセスを保持


    def create_widgets(self):
        # Settings frame
        settings_frame = ttk.LabelFrame(self.master, text="Simulation Settings")
        settings_frame.pack(padx=10, pady=10, fill="x", expand=False)

        # Prepare layout grid
        row_idx = 0

        # --fast-join
        ttk.Checkbutton(settings_frame, text="Fast Join (--fast-join)", variable=self.fast_join_var).grid(row=row_idx, column=0, sticky="w", padx=5, pady=2)
        row_idx += 1

        # --exp
        ttk.Label(settings_frame, text="Experiment Type (--exp):").grid(row=row_idx, column=0, sticky="w", padx=5, pady=2)
        exp_options = ["basic", "unicast", "unicast_vary_n"]
        exp_combobox = ttk.Combobox(settings_frame, textvariable=self.exp_var, values=exp_options, state="readonly")
        exp_combobox.grid(row=row_idx, column=1, sticky="ew", padx=5, pady=2)
        exp_combobox.bind("<<ComboboxSelected>>", self.update_widget_states)  # Update widget states when selection changes
        row_idx += 1

        # -n
        ttk.Label(settings_frame, text="Number of Nodes (-n):").grid(row=row_idx, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(settings_frame, textvariable=self.n_var).grid(row=row_idx, column=1, sticky="ew", padx=5, pady=2)
        row_idx += 1

        # --alpha
        ttk.Label(settings_frame, text="Membership Vector Base (--alpha):").grid(row=row_idx, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(settings_frame, textvariable=self.alpha_var).grid(row=row_idx, column=1, sticky="ew", padx=5, pady=2)
        row_idx += 1

        # --unicast-algorithm
        ttk.Label(settings_frame, text="Unicast Algorithm (--unicast-algorithm):").grid(row=row_idx, column=0, sticky="w", padx=5, pady=2)
        unicast_algo_options = ["greedy", "original"]
        self.unicast_algo_combobox = ttk.Combobox(settings_frame, textvariable=self.unicast_algo_var, values=unicast_algo_options, state="readonly")
        self.unicast_algo_combobox.grid(row=row_idx, column=1, sticky="ew", padx=5, pady=2)
        row_idx += 1

        # --seed
        ttk.Label(settings_frame, text="Random Seed (--seed):").grid(row=row_idx, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(settings_frame, textvariable=self.seed_var).grid(row=row_idx, column=1, sticky="ew", padx=5, pady=2)
        row_idx += 1

        # --interactive
        ttk.Checkbutton(settings_frame, text="Display Graphs in Window (--interactive)", variable=self.interactive_var).grid(row=row_idx, column=0, sticky="w", padx=5, pady=2)
        row_idx += 1

        # --output-topology-max-level
        ttk.Label(settings_frame, text="Topology Max Level (--output-topology-max-level):").grid(row=row_idx, column=0, sticky="w", padx=5, pady=2)
        self.output_topology_entry = ttk.Entry(settings_frame, textvariable=self.output_topology_max_level_var)
        self.output_topology_entry.grid(row=row_idx, column=1, sticky="ew", padx=5, pady=2)
        row_idx += 1

        # --output-hop-graph
        self.output_hop_graph_check = ttk.Checkbutton(settings_frame, text="Output Hop Graph (--output-hop-graph)", variable=self.output_hop_graph_var)
        self.output_hop_graph_check.grid(row=row_idx, column=0, sticky="w", padx=5, pady=2)
        self.output_hop_graph_check.bind("<ButtonRelease-1>", self.update_widget_states)  # Update states when checkbox is released
        row_idx += 1

        # --diagonal
        self.diagonal_check = ttk.Checkbutton(settings_frame, text="Draw Diagonal Lines on Hop Graph (--diagonal)", variable=self.diagonal_var)
        self.diagonal_check.grid(row=row_idx, column=0, sticky="w", padx=5, pady=2)
        row_idx += 1

        # -v / --verbose
        ttk.Checkbutton(settings_frame, text="Verbose Output (--verbose)", variable=self.verbose_var).grid(row=row_idx, column=0, sticky="w", padx=5, pady=2)
        row_idx += 1

        # Simulation Control Frame (シミュレーション制御用の新しいフレーム)
        control_frame = ttk.Frame(self.master)
        control_frame.pack(pady=10) # 画面中央に配置

        # Simulation Start Button (左側に配置)
        self.start_button = ttk.Button(control_frame, text="Start Simulation", command=self.start_simulation)
        self.start_button.grid(row=0, column=0, padx=5) # control_frame 内のグリッドで左に

        # Simulation Stop Button (右側に配置)
        self.stop_button = ttk.Button(control_frame, text="Stop Simulation", command=self.stop_simulation, state="disabled")
        self.stop_button.grid(row=0, column=1, padx=5) # control_frame 内のグリッドで右に

        # Results Display Area (Text widget)
        #self.results_text = tk.Text(self.master, wrap="word", height=15)
        #self.results_text.pack(padx=10, pady=5, fill="both", expand=True)
        #self.results_text.insert(tk.END, "Simulation output will be displayed here...\n")
        
        # --- ここから修正: 結果表示エリアにスクロールバーを追加 ---
        # Textウィジェットとスクロールバーを配置するためのフレーム
        self.results_frame = ttk.Frame(self.master)
        self.results_frame.pack(padx=10, pady=5, fill="both", expand=True)

        # 結果表示エリア (Textウィジェット)
        self.results_text = tk.Text(self.results_frame, wrap="word", height=15) # 親を self.results_frame に変更
        self.results_text.pack(side="left", fill="both", expand=True) # Textウィジェットを左に配置
        self.results_text.insert(tk.END, "Simulation output will be displayed here...\n")

        # 垂直スクロールバー
        self.scrollbar = ttk.Scrollbar(self.results_frame, orient="vertical", command=self.results_text.yview)
        self.scrollbar.pack(side="right", fill="y") # スクロールバーを右に配置

        # Textウィジェットとスクロールバーを連携させる
        self.results_text.config(yscrollcommand=self.scrollbar.set)
        # --- 修正ここまで ---

        # Update initial widget states
        self.update_widget_states()

    def update_widget_states(self, event=None):
        # Updates the enabled/disabled state of related widgets based on experiment type and other checkbox states
        exp_type = self.exp_var.get()
        output_hop_graph_checked = self.output_hop_graph_var.get()

        # Control enable/disable of Unicast Algorithm
        if exp_type in ["unicast", "unicast_vary_n"]:
            self.unicast_algo_combobox.config(state="readonly")  # Enable selection
        else:
            self.unicast_algo_combobox.config(state="disabled")  # Disable
            self.unicast_algo_var.set("greedy") # Reset to default if disabled

        # Control enable/disable of Topology Max Level
        if exp_type == "basic":
            self.output_topology_entry.config(state="normal")  # Enable
        else:
            self.output_topology_entry.config(state="disabled")  # Disable
            self.output_topology_max_level_var.set(0)  # Reset value to 0 if disabled

        # Control enable/disable of Hop Graph related options (--output-hop-graph, --diagonal)
        if exp_type == "unicast":
            self.output_hop_graph_check.config(state="normal")  # Enable hop graph checkbox
            if output_hop_graph_checked:  # If hop graph is checked, enable diagonal option as well
                self.diagonal_check.config(state="normal")
            else:  # If hop graph is not checked, disable diagonal option and reset its value to False
                self.diagonal_check.config(state="disabled")
                self.diagonal_var.set(False)
        else:  # For experiment types other than "unicast", disable all hop graph related options and reset values to False
            self.output_hop_graph_check.config(state="disabled")
            self.output_hop_graph_var.set(False)
            self.diagonal_check.config(state="disabled")
            self.diagonal_var.set(False)

    def start_simulation(self):
        # Method executed when the simulation start button is pressed
        self.results_text.delete(1.0, tk.END)  # Clear previous simulation output
        self.results_text.insert(tk.END, "Starting simulation...\n")
        self.start_button.config(state="disabled")  # Disable button to prevent multiple simultaneous launches
        self.stop_button.config(state="normal") # 追加: 終了ボタンを有効化

        # Construct the list of command-line arguments to pass to sg_main.py based on GUI inputs
        args_list = []
        if self.fast_join_var.get():  # If --fast-join checkbox is ON, add it
            args_list.append("--fast-join")

        args_list.extend(["--exp", self.exp_var.get()])  # Add --exp and its value

        args_list.extend(["-n", str(self.n_var.get())])  # Add -n and its value (convert integer to string)
        args_list.extend(["--alpha", str(self.alpha_var.get())])  # Add --alpha and its value

        # Add unicast algorithm only if experiment type is "unicast" or "unicast_vary_n"
        if self.exp_var.get() in ["unicast", "unicast_vary_n"]:
            args_list.extend(["--unicast-algorithm", self.unicast_algo_var.get()])

        if self.seed_var.get():  # If random seed is entered (not empty), add it
            args_list.extend(["--seed", self.seed_var.get()])

        if self.interactive_var.get():  # If --interactive checkbox is ON, add it
            args_list.append("--interactive")

        # Add topology max level only if experiment type is "basic" and level is > 0
        if self.exp_var.get() == "basic" and self.output_topology_max_level_var.get() > 0:
            args_list.extend(["--output-topology-max-level", str(self.output_topology_max_level_var.get())])

        # Add hop graph output options only if experiment type is "unicast" and hop graph output is ON
        if self.exp_var.get() == "unicast" and self.output_hop_graph_var.get():
            args_list.append("--output-hop-graph")
            if self.diagonal_var.get():  # If diagonal drawing is ON, add it
                args_list.append("--diagonal")

        if self.verbose_var.get():  # If --verbose checkbox is ON, add it
            args_list.append("--verbose")

        # Construct the path to sg_main.py
        # This GUI script (main_gui.py) is assumed to be in ~/sgsim_project/gui/
        # sg_main.py is located at ~/sgsim_project/sgsim/src/sg_main.py, so we use a relative path
        # os.path.dirname(__file__) gets the directory of the current file (~/sgsim_project/gui/)
        # Then, it constructs the path "../sgsim/src/sg_main.py"
        script_path = os.path.join(os.path.dirname(__file__), "..", "sgsim-py313", "src", "sg_main.py")

        # Command list to execute sg_main.py using the current Python interpreter (from the virtual environment)
        command = [sys.executable, script_path] + args_list

        self.results_text.insert(tk.END, f"Execution command: {' '.join(command)}\n\n")

        # Run the simulation in a separate thread to prevent the GUI from freezing
        # Using `threading.Thread`. `target` specifies the function to run, `args` passes arguments.
        simulation_thread = threading.Thread(target=self._run_simulation_in_thread, args=(command,))
        simulation_thread.daemon = True  # Set as a daemon thread so it terminates with the main (GUI) thread
        simulation_thread.start()  # Start the thread

    # 追加: シミュレーションを停止するメソッド
    def stop_simulation(self):
        if self.simulation_process and self.simulation_process.poll() is None: # プロセスが存在し、まだ実行中であれば
            # プロセスを強制終了 (SIGTERM を送る)
            # Linux (WSL) の場合
            self.simulation_process.terminate()
            self.results_text.insert(tk.END, "\nStopping simulation...\n") # 停止中メッセージ
            # 少し待ってから、まだ終了していなければ SIGKILL で強制終了
            try:
                self.simulation_process.wait(timeout=5) # 5秒待つ
            except subprocess.TimeoutExpired:
                self.simulation_process.kill() # 強制終了
                self.results_text.insert(tk.END, "\nSimulation force-killed.\n") # 強制終了メッセージ
            
        else:
            self.results_text.insert(tk.END, "\nSimulation is not running.\n") # 実行中でない場合
        
        self.stop_button.config(state="disabled") # 終了ボタンを無効化
        self.start_button.config(state="normal") # 開始ボタンを有効化 (シミュレーション終了を待たずに)
        self.simulation_process = None # プロセス参照をクリア

    def _run_simulation_in_thread(self, command):
        # Method to execute the simulation process in a separate thread and capture its output (stdout/stderr)
        try:
            # subprocess.Popen を使って新しいプロセスとしてsg_main.pyを実行
            # プロセスオブジェクトをインスタンス変数に保持
            self.simulation_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, universal_newlines=True)
            
            # 標準出力の各行をリアルタイムで読み込み、キューにプッシュ
            for line in iter(self.simulation_process.stdout.readline, ''):
                self.output_queue.put(('stdout', line))
            # 標準エラー出力の各行をリアルタイムでキューにプッシュ
            for line in iter(self.simulation_process.stderr.readline, ''):
                self.output_queue.put(('stderr', line))
            
            self.simulation_process.stdout.close()
            self.simulation_process.stderr.close()
            # process.wait() の代わりに self.simulation_process.wait() を使う
            self.simulation_process.wait() # プロセスが終了するのを待つ

            self.output_queue.put(('finished', None))

        except Exception as e:  # If a process-level error occurs during simulation execution
            self.output_queue.put(('error', str(e)))  # Send the error message to the queue
        finally:
            self.simulation_process = None # プロセス終了後に変数から参照をクリア
    def process_queue(self):
            # ... (既存のコード) ...
            try:
                while True:
                    tag, line = self.output_queue.get_nowait()
                    if tag == 'stdout':
                        self.results_text.insert(tk.END, line)
                        # 追加: 自動スクロール
                        self.results_text.see(tk.END) # 最新の行が見えるようにスクロール
                    elif tag == 'stderr':
                        self.results_text.insert(tk.END, f"ERROR: {line}")
                        self.results_text.tag_config('error', foreground='red')
                        # 追加: 自動スクロール
                        self.results_text.see(tk.END) # 最新の行が見えるようにスクロール
                    elif tag == 'finished':
                        self.results_text.insert(tk.END, "\nSimulation completed.\n")
                        self.start_button.config(state="normal")
                        self.stop_button.config(state="disabled")
                        # 追加: 自動スクロール（完了メッセージも含む）
                        self.results_text.see(tk.END)
                        
                        # ... (グラフ表示ロジックはそのまま) ...
                        break
                    elif tag == 'error':
                        self.results_text.insert(tk.END, f"\nAn error occurred during simulation: {line}\n")
                        self.start_button.config(state="normal")
                        self.stop_button.config(state="disabled")
                        # 追加: 自動スクロール（エラーメッセージも含む）
                        self.results_text.see(tk.END)
                        break
            except queue.Empty:
                pass
            finally:
                self.master.after(100, self.process_queue)

# Tkinter application execution
if __name__ == "__main__":
    # This block ensures the GUI is launched only when the script is executed directly
    root = tk.Tk()  # Create the Tkinter root window
    app = SGSimGUI(root)  # Create an instance of the SGSimGUI application
    root.mainloop()  # Start the Tkinter event loop, making the GUI visible and interactive