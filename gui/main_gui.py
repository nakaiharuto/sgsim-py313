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
        master.geometry("800x700")  # Set the initial window size (width x height)

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

        # Simulation Start Button
        self.start_button = ttk.Button(self.master, text="Start Simulation", command=self.start_simulation)
        self.start_button.pack(pady=10)

        # Results Display Area (Text widget)
        self.results_text = tk.Text(self.master, wrap="word", height=15)
        self.results_text.pack(padx=10, pady=5, fill="both", expand=True)
        self.results_text.insert(tk.END, "Simulation output will be displayed here...\n")

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

    def _run_simulation_in_thread(self, command):
        # Method to execute the simulation process in a separate thread and capture its output (stdout/stderr)
        try:
            # Use subprocess.Popen to execute sg_main.py as a new, independent process
            # stdout/stderr=subprocess.PIPE captures output via pipes
            # text=True, bufsize=1, universal_newlines=True configure text mode, unbuffered, and universal newlines
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, universal_newlines=True)

            # Push each line of standard output to the queue in real-time
            for line in iter(process.stdout.readline, ''):  # Read lines until an empty string is returned
                self.output_queue.put(('stdout', line))
            # Push each line of standard error to the queue in real-time
            for line in iter(process.stderr.readline, ''):
                self.output_queue.put(('stderr', line))

            process.stdout.close()  # Close standard output pipe
            process.stderr.close()  # Close standard error pipe
            process.wait()  # Wait for the process to terminate

            self.output_queue.put(('finished', None))  # Send a finished notification to the queue

        except Exception as e:  # If a process-level error occurs during simulation execution
            self.output_queue.put(('error', str(e)))  # Send the error message to the queue

    def process_queue(self):
        # Method run periodically on the GUI's main thread to get output from the queue and display it in the Text widget
        try:
            while True:  # Loop until the queue is empty
                tag, line = self.output_queue.get_nowait()  # Get data (tag and line) from the queue non-blockingly
                if tag == 'stdout':
                    self.results_text.insert(tk.END, line)  # Insert standard output at the end of the Text widget
                elif tag == 'stderr':
                    self.results_text.insert(tk.END, f"ERROR: {line}")  # Insert error output and set color to red
                    self.results_text.tag_config('error', foreground='red')
                elif tag == 'finished':
                    self.results_text.insert(tk.END, "\nSimulation completed.\n")  # Completion message
                    self.start_button.config(state="normal")  # Re-enable the button to allow re-running
                    break  # Exit the loop
                elif tag == 'error':
                    self.results_text.insert(tk.END, f"\nAn error occurred during simulation: {line}\n")  # Error message
                    self.start_button.config(state="normal")  # Re-enable the button
                    break  # Exit the loop
        except queue.Empty:  # Exception if the queue is empty when get_nowait() is called
            pass  # Do nothing
        finally:
            # Schedule itself to run again after 100ms to continue checking the queue
            self.master.after(100, self.process_queue)


# Tkinter application execution
if __name__ == "__main__":
    # This block ensures the GUI is launched only when the script is executed directly
    root = tk.Tk()  # Create the Tkinter root window
    app = SGSimGUI(root)  # Create an instance of the SGSimGUI application
    root.mainloop()  # Start the Tkinter event loop, making the GUI visible and interactive