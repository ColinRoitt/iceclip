import os
import time
import threading
import datetime
import requests
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
from tkinter import filedialog
import sys
import configparser

APP_NAME = "IceClipper"
FONT = "Arial"
HEADING_STYLE = (FONT, 18)
LABEL_STYLE = (FONT, 12)
VALUE_STYLE = (FONT, 10)
LARGE_BUTTON_STYLE = (FONT, 18)
ICON_BUTTON_STYLE = (FONT, 20)

# Default values
DEFAULT_ICECAST_URL = "https://audio.ury.org.uk/live-high"
DEFAULT_BUFFER_SIZE = 2
DEFAULT_PATH = "saved_clips"
DEFAULT_FILE_PREFIX = "audio"

CONFIG = "config.ini"

class AudioRecorderApp:
    def __init__(self, master):
        self.master = master
        master.title(APP_NAME)
        # set window size minimum
        master.minsize(400, 600)
        # bind keyboard shortcuts
        master.bind("<Return>", lambda e: self.save_clip() if not self.stop_flag else None)
        
        self.icon = tk.PhotoImage(file="icon.png")
        # set app iconm
        master.iconphoto(False, self.icon)
        
        # Buffer for storing audio data
        self.audio_buffer = []

        # Icecast stream URL without trailing slash
        self.ICECAST_URL = tk.StringVar()
        self.ICECAST_URL.set(DEFAULT_ICECAST_URL)

        # Sample rate
        self.SAMPLE_RATE = 48000

        # Chunk size in bytes
        self.CHUNK_SIZE = 1024

        # Buffer size in minutes
        self.buffer_size_minutes = tk.StringVar()
        self.buffer_size_minutes.set(DEFAULT_BUFFER_SIZE)

        # Flag to indicate when to stop
        self.stop_flag = True

        # Thread for capturing audio
        self.audio_capture_thread = None

        self.output_folder = tk.StringVar()
        self.output_folder.set(DEFAULT_PATH)

        self.file_prefix = tk.StringVar()
        self.file_prefix.set(DEFAULT_FILE_PREFIX)
        
        self.config = self.init_config()
        self.build_ui(master)

    def build_ui(self, master):
        # DEFINE UI ELEMENTS
        heading_container = tk.Frame(master)
        # self.icon_label = tk.Label(heading_container, image=self.icon, width=30)
        # self.icon_label.pack(pady=10, side=tk.LEFT)
        self.label = tk.Label(heading_container, text=APP_NAME, font=HEADING_STYLE)
        self.label.pack(pady=10, side=tk.LEFT)
        heading_container.pack()

        self.url_label = tk.Label(master, text="Icecast Stream URL:", justify=tk.LEFT, font=LABEL_STYLE)
        self.url_label.pack()

        self.url_entry = tk.Entry(master, width=50, textvariable=self.ICECAST_URL)
        self.url_entry.pack(pady=10)

        # display and allow changing of output folder
        self.output_folder_label = tk.Label(master, text="Output Folder:", justify=tk.LEFT, font=LABEL_STYLE)
        self.output_folder_label.pack()
        self.output_folder_entry = tk.Label(master, width=50, wraplength=300, textvariable=self.output_folder, justify=tk.LEFT, font=VALUE_STYLE)
        self.output_folder_entry.pack()

        self.output_folder_button = tk.Button(master, text="Change Folder", command=self.change_output_folder)
        self.output_folder_button.pack(pady=5)

        clip_name_container = tk.Frame(master)
        self.file_prefix_label = tk.Label(clip_name_container, text="Clip Name Prefix:", justify=tk.LEFT, font=LABEL_STYLE)
        self.file_prefix_label.pack(side=tk.LEFT, padx=5)
        self.file_prefix_entry = tk.Entry(clip_name_container, width=20, textvariable=self.file_prefix)
        self.file_prefix_entry.pack(pady=5)
        clip_name_container.pack()

        self.separator = ttk.Separator(master, orient='horizontal')
        self.separator.pack(fill='x', padx=50, pady=20)
        
        player_container = tk.Frame(master)
        self.connect_button = tk.Button(player_container, text="▶", command=self.connect, font=ICON_BUTTON_STYLE)
        self.connect_button.pack(pady=5, side=tk.LEFT)
        self.disconnect_button = tk.Button(player_container, text="■", command=self.disconnect, state=tk.DISABLED, font=ICON_BUTTON_STYLE)
        self.disconnect_button.pack(pady=5)
        player_container.pack()

        self.clip_button = tk.Button(master, text="Save Clip", command=self.save_clip, state=tk.DISABLED, height=2, width=10, font=LARGE_BUTTON_STYLE)
        self.clip_button.pack(ipadx=10, pady=5)

        self.output_folder_entry = tk.Label(master, text="Tip: You can use the 'enter' key to quickly save a clip", justify=tk.LEFT, font=VALUE_STYLE)
        self.output_folder_entry.pack()

        self.separator_2 = ttk.Separator(master, orient='horizontal')
        self.separator_2.pack(fill='x', padx=50, pady=20)

        self.progress_label = tk.Label(master, text="Buffer Fullness:", justify=tk.LEFT, font=LABEL_STYLE)
        self.progress_label.pack()
        self.progress_bar = ttk.Progressbar(master, orient="horizontal", length=200, mode="determinate")
        self.progress_bar.pack()

        buffer_size_container = tk.Frame(master)
        self.buffer_size_label = tk.Label(buffer_size_container, text="Buffer Size (minutes):", justify=tk.LEFT, font=LABEL_STYLE)
        self.buffer_size_label.pack(side=tk.LEFT, padx=5)
        self.buffer_size_entry = tk.Entry(buffer_size_container, width=10, textvariable=self.buffer_size_minutes)
        self.buffer_size_entry.pack(pady=5)
        # enfore integer input
        self.buffer_size_entry.config(validate="key", validatecommand=(self.buffer_size_entry.register(lambda s: s.isdigit()), "%S"))
        buffer_size_container.pack()

        self.status_label = tk.Label(master, text="", font=LABEL_STYLE)
        self.status_label.pack(pady=10, padx=5)

    def save_settings(self, setting, value):
        config = configparser.ConfigParser()
        config.read(CONFIG)
        config.set("DEFAULT", setting, str(value))
        with open(CONFIG, "w") as f:
            config.write(f)
    
    def init_config(self):
        # if no config file create one
        if not os.path.exists(CONFIG):
            with open(CONFIG, "w") as f:
                f.write("[DEFAULT]\n")
                f.write(f"ICECAST_URL={DEFAULT_ICECAST_URL}\n")
                f.write(f"BUFFER_SIZE={DEFAULT_BUFFER_SIZE}\n")
                f.write(f"OUTPUT_FOLDER={DEFAULT_PATH}\n")
                f.write(f"FILE_PREFIX={DEFAULT_FILE_PREFIX}\n")

        # load settings
        config = configparser.ConfigParser()
        config.read(CONFIG)
        self.ICECAST_URL.set(config.get("DEFAULT", "ICECAST_URL"))
        self.buffer_size_minutes.set(config.get("DEFAULT", "BUFFER_SIZE"))
        self.output_folder.set(config.get("DEFAULT", "OUTPUT_FOLDER"))
        self.file_prefix.set(config.get("DEFAULT", "FILE_PREFIX"))

        # save setting on write of variable
        self.ICECAST_URL.trace_add("write", lambda *args: self.save_settings("ICECAST_URL", self.ICECAST_URL.get()))
        self.buffer_size_minutes.trace_add("write", lambda *args: self.save_settings("BUFFER_SIZE", self.buffer_size_minutes.get()))
        self.output_folder.trace_add("write", lambda *args: self.save_settings("OUTPUT_FOLDER", self.output_folder.get()))
        self.file_prefix.trace_add("write", lambda *args: self.save_settings("FILE_PREFIX", self.file_prefix.get()))

        return config
    
    def get_max_buffer_size(self):
        int_buffer = int(self.buffer_size_minutes.get())
        return int((int_buffer / 2) * 60 * self.SAMPLE_RATE / self.CHUNK_SIZE)

    def connect(self):
        url = self.ICECAST_URL.get()
        if not url:
            messagebox.showerror("Error", "Please enter a valid URL.")
            return

        buffer_size_str = self.buffer_size_entry.get()
        if not buffer_size_str.isdigit():
            messagebox.showerror("Error", "Please enter a valid buffer size (integer).")
            return

        buffer_size = int(buffer_size_str)
        if buffer_size <= 0:
            messagebox.showerror("Error", "Please enter a positive buffer size.")
            return

        self.audio_buffer = []
        self.update_progress()
        self.stop_flag = False
        self.update_status(f"Connecting to {url}")
        self.audio_capture_thread = threading.Thread(target=self.capture_audio)
        self.audio_capture_thread.start()
        self.connect_button.config(state=tk.DISABLED)
        self.disconnect_button.config(state=tk.NORMAL)
        self.clip_button.config(state=tk.NORMAL)
        self.buffer_size_entry.config(state=tk.DISABLED)
    
    def disconnect(self):
        # self.audio_capture_thread.join()
        self.stop_flag = True
        self.update_status(f"Disconnected from {self.ICECAST_URL.get()}")
        self.connect_button.config(state=tk.NORMAL)
        self.disconnect_button.config(state=tk.DISABLED)
        self.clip_button.config(state=tk.DISABLED)
        self.buffer_size_entry.config(state=tk.NORMAL)
        self.audio_buffer = []
        self.update_progress()

    def capture_audio(self):
        self.update_status(f"Listening... (audio from {self.ICECAST_URL.get()})")
        while not self.stop_flag:
            try:
                response = requests.get(self.ICECAST_URL.get(), stream=True, timeout=10)
                if response.status_code == 200:
                    for chunk in response.iter_content(chunk_size=self.CHUNK_SIZE):
                        if chunk:
                            self.audio_buffer.append(chunk)
                            if self.stop_flag:
                                sys.exit()
                            self.update_progress()
                            if len(self.audio_buffer) >= self.get_max_buffer_size():
                                # Remove excess chunks to maintain buffer size
                                excess_chunks = len(self.audio_buffer) - self.get_max_buffer_size()
                                self.audio_buffer = self.audio_buffer[excess_chunks:]
            except Exception as e:
                self.update_status(f"Error capturing audio: {e}")
            time.sleep(1)

    def change_output_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_folder.set(folder)
            
    def save_clip(self):
        threading.Thread(target=self.save_audio_clip).start()

    def save_audio_clip(self):
        # make folder if it doesn't exist
        of = self.output_folder.get()
        if not os.path.exists(of):
            os.makedirs(of)
        current_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        fp = self.file_prefix.get()
        filename = f"{fp}_{current_time}.wav"
        full_audio = b''.join(self.audio_buffer)
        with open(f'{of}/{filename}', 'wb') as f:
            f.write(full_audio)
        self.update_status(f"Audio clip saved to {filename}")

    def update_status(self, message):
        self.status_label.config(text=message)

    def update_progress(self):
        buffer_size = len(self.audio_buffer)
        progress = min(100 * (buffer_size / self.get_max_buffer_size()), 100)
        self.progress_bar['value'] = progress
        self.master.update_idletasks()

def main():
    root = tk.Tk()
    root.protocol("WM_DELETE_WINDOW", lambda: exit())
    app = AudioRecorderApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
