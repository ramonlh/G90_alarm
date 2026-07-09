#!/usr/bin/env python3
import json
import os
import tkinter as tk
from tkinter import ttk, filedialog
from datetime import datetime
from pathlib import Path

DEFAULT_LOG = Path.home() / "alarma" / "g90_eventos_base.jsonl"

ARM_STATES = {
    "ARMADO TOTAL",
    "ARMADO PARCIAL",
    "DESARMADO",
    "ARMADO TOTAL DESDE MANDO",
    "ARMADO PARCIAL DESDE MANDO",
    "DESARMADO DESDE MANDO",
}

ZONE_STATES = {
    "ZONA CABLEADA 1 - ACTIVADA": 1,
    "ZONA CABLEADA 2 - ACTIVADA": 2,
    "ZONA CABLEADA 3 - ACTIVADA": 3,
    "ZONA CABLEADA 4 - ACTIVADA": 4,
}

SOS_STATES = {
    "SOS",
    "SOS DESDE MANDO - DETALLE ORIGEN",
    "SOS DESDE PANEL - DETALLE ORIGEN",
}

def parse_iso(text: str):
    try:
        return datetime.fromisoformat(text)
    except Exception:
        return None

def now_local():
    return datetime.now().astimezone()

class G90PanelEstado(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Estado alarma G90")
        self.geometry("980x700")
        self.minsize(860, 620)

        self.log_path = DEFAULT_LOG
        self.file_pos = 0
        self.last_mtime = None
        self.current_arm_state = "DESCONOCIDO"
        self.current_arm_source = "-"
        self.last_event_text = "-"
        self.last_event_time = None
        self.last_device_packet_time = None
        self.last_upstream_packet_time = None
        self.last_sos = "-"
        self.zone_status = {
            1: {"state": "REPOSO", "time": None},
            2: {"state": "REPOSO", "time": None},
            3: {"state": "REPOSO", "time": None},
            4: {"state": "REPOSO", "time": None},
        }

        self._build_ui()
        self.after(300, self.poll_file)

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        top = ttk.Frame(self, padding=10)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="Fichero de eventos:", font=("TkDefaultFont", 10, "bold")).grid(row=0, column=0, sticky="w")
        self.path_var = tk.StringVar(value=str(self.log_path))
        ttk.Entry(top, textvariable=self.path_var).grid(row=0, column=1, sticky="ew", padx=(8, 8))
        ttk.Button(top, text="Cambiar...", command=self.choose_file).grid(row=0, column=2, sticky="e")

        summary = ttk.Frame(self, padding=(10, 0, 10, 10))
        summary.grid(row=1, column=0, sticky="ew")
        for i in range(4):
            summary.columnconfigure(i, weight=1)

        self.arm_label = tk.Label(summary, text="DESCONOCIDO", font=("TkDefaultFont", 22, "bold"), relief="groove", padx=16, pady=12)
        self.arm_label.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=(0, 8), pady=(0, 8))

        self.conn_label = tk.Label(summary, text="SIN DATOS", font=("TkDefaultFont", 16, "bold"), relief="groove", padx=16, pady=12)
        self.conn_label.grid(row=0, column=2, columnspan=2, sticky="nsew", pady=(0, 8))

        info = ttk.Frame(summary)
        info.grid(row=1, column=0, columnspan=4, sticky="ew")
        info.columnconfigure(1, weight=1)

        ttk.Label(info, text="Origen último estado:").grid(row=0, column=0, sticky="w")
        self.arm_source_var = tk.StringVar(value="-")
        ttk.Label(info, textvariable=self.arm_source_var).grid(row=0, column=1, sticky="w")

        ttk.Label(info, text="Último evento:").grid(row=1, column=0, sticky="w")
        self.last_event_var = tk.StringVar(value="-")
        ttk.Label(info, textvariable=self.last_event_var).grid(row=1, column=1, sticky="w")

        ttk.Label(info, text="Último SOS:").grid(row=2, column=0, sticky="w")
        self.last_sos_var = tk.StringVar(value="-")
        ttk.Label(info, textvariable=self.last_sos_var).grid(row=2, column=1, sticky="w")

        zones = ttk.LabelFrame(self, text="Zonas cableadas", padding=10)
        zones.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        for i in range(4):
            zones.columnconfigure(i, weight=1)

        self.zone_labels = {}
        for i in range(1, 5):
            frame = ttk.Frame(zones, padding=4)
            frame.grid(row=0, column=i-1, sticky="nsew", padx=6)
            ttk.Label(frame, text=f"Zona {i}", font=("TkDefaultFont", 11, "bold")).pack()
            lbl = tk.Label(frame, text="REPOSO", font=("TkDefaultFont", 16, "bold"), relief="ridge", padx=10, pady=8)
            lbl.pack(fill="x", pady=6)
            time_var = tk.StringVar(value="Sin eventos")
            ttk.Label(frame, textvariable=time_var).pack()
            self.zone_labels[i] = (lbl, time_var)

        buttons = ttk.Frame(self, padding=(10, 0, 10, 10))
        buttons.grid(row=4, column=0, sticky="ew")
        ttk.Button(buttons, text="Reset visual zonas", command=self.reset_zones).pack(side="left")
        ttk.Button(buttons, text="Recargar desde cero", command=self.reload_full).pack(side="left", padx=(8, 0))

        log_frame = ttk.LabelFrame(self, text="Eventos recientes", padding=10)
        log_frame.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 10))
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        self.log_text = tk.Text(log_frame, wrap="word", height=18)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        yscroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        yscroll.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=yscroll.set)
        self.log_text.configure(state="disabled")

        self.refresh_ui()

    def choose_file(self):
        filename = filedialog.askopenfilename(
            title="Selecciona fichero JSONL de eventos",
            filetypes=[("JSONL", "*.jsonl"), ("Todos", "*.*")]
        )
        if filename:
            self.log_path = Path(filename)
            self.path_var.set(str(self.log_path))
            self.reload_full()

    def reload_full(self):
        self.file_pos = 0
        self.last_mtime = None
        self.current_arm_state = "DESCONOCIDO"
        self.current_arm_source = "-"
        self.last_event_text = "-"
        self.last_event_time = None
        self.last_device_packet_time = None
        self.last_upstream_packet_time = None
        self.last_sos = "-"
        self.zone_status = {
            1: {"state": "REPOSO", "time": None},
            2: {"state": "REPOSO", "time": None},
            3: {"state": "REPOSO", "time": None},
            4: {"state": "REPOSO", "time": None},
        }
        self.clear_log()
        self.poll_file(force=True)

    def reset_zones(self):
        for i in range(1, 5):
            self.zone_status[i] = {"state": "REPOSO", "time": None}
        self.refresh_ui()

    def clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def append_log(self, text: str):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text + "\n")
        lines = int(self.log_text.index("end-1c").split(".")[0])
        if lines > 300:
            self.log_text.delete("1.0", f"{lines-300}.0")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def refresh_ui(self):
        state = self.current_arm_state
        if state.startswith("ARMADO TOTAL"):
            self.arm_label.configure(bg="#d9534f", fg="white")
        elif state.startswith("ARMADO PARCIAL"):
            self.arm_label.configure(bg="#f0ad4e", fg="black")
        elif state.startswith("DESARMADO"):
            self.arm_label.configure(bg="#5cb85c", fg="white")
        else:
            self.arm_label.configure(bg="#cccccc", fg="black")
        self.arm_label.configure(text=state)
        self.arm_source_var.set(self.current_arm_source)
        self.last_event_var.set(self.last_event_text)
        self.last_sos_var.set(self.last_sos)

        conn_text, conn_bg, conn_fg = self.connection_status()
        self.conn_label.configure(text=conn_text, bg=conn_bg, fg=conn_fg)

        for i in range(1, 5):
            lbl, time_var = self.zone_labels[i]
            st = self.zone_status[i]["state"]
            tm = self.zone_status[i]["time"]
            if st == "ACTIVADA":
                lbl.configure(text="ACTIVADA", bg="#d9534f", fg="white")
            else:
                lbl.configure(text="REPOSO", bg="#5cb85c", fg="white")
            time_var.set(tm if tm else "Sin eventos")

    def connection_status(self):
        ref = self.last_device_packet_time or self.last_event_time
        if not ref:
            return "SIN DATOS", "#cccccc", "black"
        age = (now_local() - ref.astimezone()).total_seconds()
        if age < 90:
            return "RECIBIENDO", "#5cb85c", "white"
        if age < 240:
            return "SIN TRÁFICO RECIENTE", "#f0ad4e", "black"
        return "DESCONECTADO / SILENCIOSO", "#d9534f", "white"

    def process_event(self, event: dict):
        ts = event.get("ts", "")
        kind = event.get("kind", "")
        state = event.get("state", "")

        parsed_ts = parse_iso(ts)
        if parsed_ts:
            self.last_event_time = parsed_ts

        if kind == "status_raw":
            self.last_event_text = f"{ts} | {state}"
            if state in ARM_STATES:
                self.current_arm_state = state
                self.current_arm_source = "raw"
            if state in SOS_STATES:
                self.last_sos = f"{ts} | {state}"
            if state in ZONE_STATES:
                zone = ZONE_STATES[state]
                self.zone_status[zone]["state"] = "ACTIVADA"
                self.zone_status[zone]["time"] = ts

        elif kind == "armdisarm":
            st = event.get("state", "")
            self.current_arm_state = st
            self.current_arm_source = "callback"
            self.last_event_text = f"{ts} | {st}"

        elif kind == "watchdog":
            ldp = event.get("last_device_packet_time")
            self.last_device_packet_time = parse_iso(ldp) if ldp and ldp != "None" else None
            lup = event.get("last_upstream_packet_time")
            self.last_upstream_packet_time = parse_iso(lup) if lup and lup != "None" else None

        self.append_log(self.format_event_line(event))
        self.refresh_ui()

    def format_event_line(self, event: dict):
        ts = event.get("ts", "")
        kind = event.get("kind", "")
        if kind == "status_raw":
            return f"{ts} | RAW | {event.get('state','')} | code={event.get('code_hex','')}"
        if kind == "armdisarm":
            return f"{ts} | CALLBACK | {event.get('state','')}"
        if kind == "watchdog":
            return f"{ts} | WATCHDOG | last_device={event.get('last_device_packet_time')} upstream={event.get('last_upstream_packet_time')}"
        return f"{ts} | {kind} | {json.dumps(event, ensure_ascii=False)}"

    def poll_file(self, force=False):
        try:
            if self.log_path.exists():
                mtime = os.path.getmtime(self.log_path)
                if force or self.last_mtime is None or mtime != self.last_mtime:
                    self.last_mtime = mtime
                    with open(self.log_path, "r", encoding="utf-8") as f:
                        f.seek(self.file_pos)
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                event = json.loads(line)
                                self.process_event(event)
                            except Exception as e:
                                self.append_log(f"ERROR leyendo línea: {e} | {line}")
                        self.file_pos = f.tell()
        except FileNotFoundError:
            self.last_event_var.set("Esperando fichero de eventos...")
            self.refresh_ui()
        except Exception as e:
            self.append_log(f"ERROR general: {e}")

        self.after(1000, self.poll_file)

if __name__ == "__main__":
    app = G90PanelEstado()
    app.mainloop()
