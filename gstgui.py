import subprocess, threading, os, signal, shlex
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, simpledialog


class RtspCamApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("RTSP to Virtual Camera")
        # self.overrideredirect(True)  # custom title bar
        self.geometry("640x480")
        self.resizable(False, True)
        self.proc = None
        self._build_ui()
        self._make_window_draggable()
        self._apply_dark_theme()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        # ttk.Style().theme_use("clam")
    
        # theme helper ----------------------------------------------------------- 
    def _apply_dark_theme(self):
        """Configure ttk widgets for a dark appearance."""
        style = ttk.Style(self)

        style.theme_use("clam")

        # General background / foreground
        dark_bg   = "#2b2b2b"
        dark_fg   = "#e0e0e0"
        accent    = "#4a90e2"   # button/selection accent
        entry_bg  = "#3c3f41"
        entry_fg  = "#ffffff"
        border    = "#555555"

        # Root window background
        self.configure(background=dark_bg)

        # ----- ttk widget colours ------------------------------------------------
        style.configure(".",                     # default for all ttk widgets
                        background=dark_bg,
                        foreground=dark_fg,
                        bordercolor=border,
                        focusthickness=1,
                        focuscolor=accent)

        # Buttons
        style.configure("TButton",
                        background=dark_bg,
                        foreground=dark_fg,
                        padding=5)

        style.map("TButton",
                background=[("active", accent), ("pressed", "#357ABD")],
                foreground=[("disabled", "#777777")])

        # Labels (including ScrolledText label)
        style.configure("TLabel", background=dark_bg, foreground=dark_fg)

        # Entry 
        style.configure("TEntry",
                        fieldbackground=entry_bg,
                        foreground=entry_fg,
                        padding=3, insertcolor=entry_fg)

        # Spinbox
        style.configure("TSpinbox",
                        fieldbackground=entry_bg,
                        foreground=entry_fg,
                        padding=3, insertcolor=entry_fg)

        # Scrollbar
        style.configure("Vertical.TScrollbar",
                        background=border,
                        troughcolor=dark_bg,
                        arrowcolor=dark_fg)

        # ScrolledText uses a regular Text widget; set its colors manually
        self.option_add("*Text.background", entry_bg)
        self.option_add("*Text.foreground", entry_fg)
        self.option_add("*Text.insertBackground", dark_fg)

    # -----------------------------------------------------------------
    def _build_ui(self):
        # main panel
        main = ttk.Frame(self, padding=10)
        main.pack(fill="both", expand=True)

        # RTSP URL
        ttk.Label(main, text="Enter RTSP URL:").grid(row=0, column=0, sticky="w")
        self.url_var = tk.StringVar()
        self.url_entry = ttk.Entry(main, textvariable=self.url_var, width=40)
        self.url_entry.grid(row=0, column=1, columnspan=4, sticky="ew", pady=4)

        # V4L2 device number
        ttk.Label(main, text="Virtual Camera: /dev/video").grid(
            row=1, column=0, sticky="w"
        )

        # device‑number spinbox
        self.dev_num_var = tk.IntVar(value=10)
        self.dev_spinbox = ttk.Spinbox(
            main,
            from_=0,
            to=63,
            textvariable=self.dev_num_var,
            width=5,
        )
        self.dev_spinbox.grid(row=1, column=1, sticky="w", pady=4, padx=(0, 4))

        ttk.Label(main, text="Camera name:").grid(
            row=1, column=2, sticky="w", pady=4, padx=(0, 4)
        )

        self.Camera_label_var = tk.StringVar(value="RTSP-Cam")
        self.Camera_entry = ttk.Entry(main, textvariable=self.Camera_label_var, width=12)
        self.Camera_entry.grid(row=1, column=3, sticky="w", pady=4, padx=(0, 4))

        # register button
        self.register_btn = ttk.Button(
            main, text="Register Device", command=self.register_device
        )
        self.register_btn.grid(row=1, column=4, sticky="w", pady=4)


        # When the device number changes, update whether registration is allowed
        try:
            self.dev_num_var.trace_add("write", lambda *a: self._update_register_button_state())
        except Exception:
            self.dev_num_var.trace_add("w", lambda *a: self._update_register_button_state())

        # Initialize register button state based on whether device exists
        self._update_register_button_state()

        # Make sure the window and the first entry can receive keyboard focus
        try:
            self.focus_force()
            self.url_entry.focus_set()
        except Exception:
            pass

        # Start / Stop buttons
        self.start_btn = ttk.Button(main, text="Start", command=self.start_pipeline)
        self.start_btn.grid(row=3, column=0, pady=8)

        self.stop_btn = ttk.Button(
            main, text="Stop", command=self.stop_pipeline, state="disabled"
        )
        self.stop_btn.grid(row=3, column=1, pady=8)

        # Log window
        ttk.Label(main, text="Log:").grid(row=4, column=0, columnspan=3, sticky="w")
        self.log = scrolledtext.ScrolledText(main, height=18, state="disabled",background="#3c3f41", foreground="#e0e0e0",insertbackground="#e0e0e0")
        self.log.grid(row=5, column=0, columnspan=5, sticky="nsew")
        main.rowconfigure(5, weight=1)
        main.columnconfigure(1, weight=1)

    # -----------------------------------------------------------------
    def _make_window_draggable(self):
        def start_move(event):
            self._x_offset = event.x
            self._y_offset = event.y

        def do_move(event):
            x = self.winfo_pointerx() - self._x_offset
            y = self.winfo_pointery() - self._y_offset
            self.geometry(f"+{x}+{y}")

    # -----------------------------------------------------------------
    def _append_log(self, txt):
        self.log.configure(state="normal")
        self.log.insert(tk.END, txt)
        self.log.see(tk.END)
        self.log.configure(state="disabled")

    # -----------------------------------------------------------------
    def _device_exists(self, num: int) -> bool:
        """Return True if /dev/video{num} exists."""
        try:
            return os.path.exists(f"/dev/video{int(num)}")
        except Exception:
            return False

    def _update_register_button_state(self):
        """Enable the Register button only when the chosen device does not exist."""
        try:
            dev_num = int(self.dev_num_var.get())
        except Exception:
            self.register_btn.configure(state="disabled")
            return

        if self._device_exists(dev_num):
            self.register_btn.configure(state="disabled")
        else:
            self.register_btn.configure(state="normal")

    # -----------------------------------------------------------------
    def register_device(self):
        """Create a v4l2loopback device with the chosen number."""
        try:
            dev_num = int(self.dev_num_var.get())
        except Exception:
            messagebox.showerror("Input error", "Invalid device number")
            return

        self.dev_path = f"/dev/video{dev_num}"
        label = (self.Camera_label_var.get() or "RTSP-Cam").strip()
        label_quoted = shlex.quote(label)

        # -------------------------------------
        pswd = simpledialog.askstring(
            "Sudo password",
            "Enter your sudo password (will not be stored):",
            show="*",
        )
        if pswd is None:          # user cancelled
            return

        # only way to remove is modprobe -r v4l2loopback, cant add multiple devices after loading
        # ----  using -S to read password from stdin --
        cmd = (
            f"sudo -S modprobe v4l2loopback devices=1 video_nr={dev_num} card_label=\"{label_quoted}\" exclusive_caps=1"
        )
        self._append_log(f"$ {cmd}\n")

        # ----  Run it in a background thread -------------------------
        def _run_modprobe():
            try:
                result = subprocess.run(
                    cmd,
                    shell=True,
                    input=pswd + "\n",
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    # self.dev_path_var.set(dev_path)
                    self._append_log(f"Device created: /dev/video{dev_num}\n")
                    self._update_register_button_state()
                else:
                    self._append_log(
                        f"Error ({result.returncode}): {result.stderr}\n"
                    )
            except Exception as e:
                self._append_log(f"Exception: {e}\n")

        threading.Thread(target=_run_modprobe, daemon=True).start()

    # -----------------------------------------------------------------
    def _run_gst(self, cmd):
        self._append_log(f"$ {cmd}\n")
        try:
            self.proc = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid,
                text=True,
                bufsize=1,
            )
            for line in self.proc.stdout:
                self._append_log(line)
        except Exception as e:
            self._append_log(f"Error: {e}\n")
        finally:
            self._finalize_pipeline()

    # -----------------------------------------------------------------
    def _finalize_pipeline(self):
        self.proc = None
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self._append_log("\n--- pipeline terminated ---\n")

    # -----------------------------------------------------------------
    def start_pipeline(self):
        url = self.url_var.get().strip()
        dev = f"/dev/video{self.dev_num_var.get()}"
        if not url:
            messagebox.showerror("Input error", "Please enter an RTSP URL.")
            return
        if not os.path.exists(dev):
            messagebox.showerror(
                "Device error", f"{dev} does not exist. Register it first."
            )
            return

        gst_cmd = (
            f"gst-launch-1.0 -e rtspsrc location={url} latency=0 protocols=tcp name=src ! rtpjitterbuffer ! decodebin ! videoconvert ! v4l2sink device={dev} sync=false"
        )
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        threading.Thread(target=self._run_gst, args=(gst_cmd,), daemon=True).start()

    # -----------------------------------------------------------------
    def stop_pipeline(self):
        if self.proc and self.proc.poll() is None:
            self._append_log("\n--- stopping pipeline (SIGINT) ---\n")
            try:
                # self.proc.send_signal(signal.SIGINT)
                os.killpg(self.proc.pid, signal.SIGINT)
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._append_log("Process did not exit, sending SIGKILL...\n")
                os.killpg(self.proc.pid, signal.SIGKILL)
                self.proc.wait()
        self._finalize_pipeline()

    # -----------------------------------------------------------------
    def _on_close(self):
        self.stop_pipeline()
        self.destroy()


if __name__ == "__main__":
    app = RtspCamApp()
    app.mainloop()
