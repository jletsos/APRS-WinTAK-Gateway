import socket
import struct
import re
import datetime
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import xml.etree.ElementTree as ET

class APRSWinTAKApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("APRS to WinTAK Gateway (True TAK Server Edition)")
        self.geometry("1000x700")
        self.minsize(800, 500)

        # Network & Thread State
        self.running = False
        self.kiss_thread = None
        self.tak_thread = None
        self.kiss_sock = None
        self.tak_server_sock = None
        self.tak_client_conn = None  

        # Thread-safe copies of UI variables
        self.my_call = ""
        self.map_all_flag = False

        self.cot_types = {
            "Ground Unit (Default)": "a-f-G-U-C",
            "Civilian Vehicle": "a-f-G-E-V-C",
            "Truck / SUV": "a-f-G-E-V-T",
            "Radio / Comm Node": "a-f-G-U-U-a",
            "Static Sensor / Digipeater": "a-f-S-X",
            "Aircraft": "a-f-A-C-F"
        }

        self.whitelist = {} 

        self.setup_ui()

    def setup_ui(self):
        conn_frame = ttk.LabelFrame(self, text="Connection Settings", padding=10)
        conn_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(conn_frame, text="My Callsign (TX):").grid(row=0, column=0, sticky="e", padx=2)
        self.entry_mycall = ttk.Entry(conn_frame, width=12)
        self.entry_mycall.insert(0, "K5JGL-1")
        self.entry_mycall.grid(row=0, column=1, padx=5)

        ttk.Label(conn_frame, text="SoundModem Host:").grid(row=0, column=2, sticky="e", padx=2)
        self.entry_host = ttk.Entry(conn_frame, width=12)
        self.entry_host.insert(0, "127.0.0.1")
        self.entry_host.grid(row=0, column=3, padx=5)

        ttk.Label(conn_frame, text="KISS Port:").grid(row=0, column=4, sticky="e", padx=2)
        self.entry_kiss_port = ttk.Entry(conn_frame, width=6)
        self.entry_kiss_port.insert(0, "8001")
        self.entry_kiss_port.grid(row=0, column=5, padx=5)

        self.btn_toggle = ttk.Button(conn_frame, text="Start Bridge", command=self.toggle_bridge)
        self.btn_toggle.grid(row=0, column=6, padx=15)

        self.lbl_status = ttk.Label(conn_frame, text="Status: Stopped", foreground="red")
        self.lbl_status.grid(row=0, column=7, padx=5)

        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill="both", expand=True, padx=10, pady=5)

        wl_frame = ttk.LabelFrame(paned, text="Callsign Whitelist & Markers", padding=10)
        paned.add(wl_frame, weight=1)

        self.map_all_var = tk.BooleanVar(value=False)
        chk_map_all = ttk.Checkbutton(wl_frame, text="Map ALL Callsigns (Uses Default Icon)", variable=self.map_all_var, command=self.update_map_all_flag)
        chk_map_all.pack(anchor="w", pady=(0, 5))

        entry_subframe = ttk.Frame(wl_frame)
        entry_subframe.pack(fill="x", pady=5)

        self.entry_callsign = ttk.Entry(entry_subframe, width=12)
        self.entry_callsign.pack(side="left", padx=(0, 5))
        self.entry_callsign.bind("<Return>", lambda event: self.add_callsign())

        self.combo_marker = ttk.Combobox(entry_subframe, values=list(self.cot_types.keys()), state="readonly", width=18)
        self.combo_marker.current(1) 
        self.combo_marker.pack(side="left", padx=(0, 5))

        btn_add = ttk.Button(entry_subframe, text="Add", width=4, command=self.add_callsign)
        btn_add.pack(side="right")

        self.wl_listbox = tk.Listbox(wl_frame, selectmode=tk.SINGLE)
        self.wl_listbox.pack(fill="both", expand=True, pady=5)
        self.refresh_whitelist_ui()

        btn_remove = ttk.Button(wl_frame, text="Remove Selected", command=self.remove_callsign)
        btn_remove.pack(fill="x")

        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=3)

        self.notebook = ttk.Notebook(right_frame)
        self.notebook.pack(fill="both", expand=True)

        tab_positions = ttk.Frame(self.notebook)
        self.notebook.add(tab_positions, text="Live Positions")
        cols = ("time", "callsign", "lat", "lon", "cot_sent")
        self.tree_pos = ttk.Treeview(tab_positions, columns=cols, show="headings")
        for col in cols:
            self.tree_pos.heading(col, text=col.title().replace("_", " "))
            self.tree_pos.column(col, width=100)
        self.tree_pos.pack(side="left", fill="both", expand=True)

        tab_msg = ttk.Frame(self.notebook)
        self.notebook.add(tab_msg, text="APRS Messages")
        self.txt_messages = scrolledtext.ScrolledText(tab_msg, state="disabled", wrap="word")
        self.txt_messages.pack(fill="both", expand=True)

        tab_log = ttk.Frame(self.notebook)
        self.notebook.add(tab_log, text="System Log")
        self.txt_log = scrolledtext.ScrolledText(tab_log, state="disabled", wrap="word")
        self.txt_log.pack(fill="both", expand=True)

    def update_map_all_flag(self):
        self.map_all_flag = self.map_all_var.get()

    def refresh_whitelist_ui(self):
        self.wl_listbox.delete(0, tk.END)
        rev_cot = {v: k for k, v in self.cot_types.items()}
        for cs, c_type in sorted(self.whitelist.items()):
            friendly_name = rev_cot.get(c_type, "Unknown")
            self.wl_listbox.insert(tk.END, f"{cs}  [{friendly_name}]")

    def add_callsign(self):
        cs = self.entry_callsign.get().strip().upper()
        if cs:
            marker_name = self.combo_marker.get()
            self.whitelist[cs] = self.cot_types.get(marker_name, "a-f-G-U-C")
            self.entry_callsign.delete(0, tk.END)
            self.refresh_whitelist_ui()

    def remove_callsign(self):
        sel = self.wl_listbox.curselection()
        if sel:
            cs = self.wl_listbox.get(sel[0]).split("  [")[0]
            if cs in self.whitelist:
                del self.whitelist[cs]
            self.refresh_whitelist_ui()

    def log_msg(self, text):
        self.txt_log.config(state="normal")
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.txt_log.insert(tk.END, f"[{ts}] {text}\n")
        self.txt_log.see(tk.END)
        self.txt_log.config(state="disabled")

    def log_aprs_text_message(self, src, target, message, is_tx=False):
        self.txt_messages.config(state="normal")
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        prefix = "[TX OUT]" if is_tx else "[RX IN ]"
        self.txt_messages.insert(tk.END, f"[{ts}] {prefix} {src} -> {target}: {message}\n")
        self.txt_messages.see(tk.END)
        self.txt_messages.config(state="disabled")

    def toggle_bridge(self):
        if not self.running:
            self.start_bridge()
        else:
            self.stop_bridge()

    def start_bridge(self):
        host = self.entry_host.get().strip()
        try:
            kiss_port = int(self.entry_kiss_port.get().strip())
        except ValueError:
            messagebox.showerror("Error", "Port must be an integer.")
            return

        self.my_call = self.entry_mycall.get().strip().upper()
        self.map_all_flag = self.map_all_var.get()
        self.running = True
        self.btn_toggle.config(text="Stop Bridge")
        self.lbl_status.config(text="Status: Connected", foreground="green")

        self.kiss_thread = threading.Thread(target=self.kiss_listener_loop, args=(host, kiss_port), daemon=True)
        self.kiss_thread.start()

        self.tak_thread = threading.Thread(target=self.tak_server_loop, daemon=True)
        self.tak_thread.start()

    def stop_bridge(self):
        self.running = False
        try:
            if self.kiss_sock: self.kiss_sock.close()
            if self.tak_client_conn: self.tak_client_conn.close()
            if self.tak_server_sock: self.tak_server_sock.close()
        except: pass
        self.btn_toggle.config(text="Start Bridge")
        self.lbl_status.config(text="Status: Stopped", foreground="red")
        self.log_msg("[NET] Bridge stopped by user.")

    # --- THREAD 1: RECEIVE FROM RADIO (KISS) ---
    def kiss_listener_loop(self, host, kiss_port):
        try:
            self.kiss_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.kiss_sock.settimeout(2.0)
            self.kiss_sock.connect((host, kiss_port))
            self.after(0, self.log_msg, "[NET] Connected to SoundModem KISS port.")
        except Exception as e:
            self.after(0, self.log_msg, f"[ERROR] Failed to connect: {e}")
            self.after(0, self.stop_bridge)
            return

        buffer = bytearray()
        while self.running:
            try:
                chunk = self.kiss_sock.recv(1024)
                if not chunk: 
                    self.after(0, self.log_msg, "[NET] SoundModem disconnected.")
                    break
                buffer.extend(chunk)

                while b'\xc0' in buffer:
                    idx = buffer.index(b'\xc0')
                    frame = buffer[:idx]
                    buffer = buffer[idx + 1:]
                    
                    if len(frame) >= 15 and frame[0] == 0x00:
                        try:
                            self.process_ax25_rx_frame(frame)
                        except Exception as ex:
                            self.after(0, self.log_msg, f"[RX FRAME ERROR] Caught error preventing crash: {ex}")
            except socket.timeout: 
                continue
            except Exception as e: 
                if self.running:
                    self.after(0, self.log_msg, f"[NET ERROR] Socket error: {e}")
                break
                
        self.after(0, self.stop_bridge)

    def process_ax25_rx_frame(self, frame):
        src_call = self.decode_ax25_callsign(frame[8:15])
        payload = frame[15:].decode('latin-1', errors='ignore')

        msg_match = re.search(r':([A-Z0-9\-_ ]{3,9}):(.*)', payload)
        if msg_match:
            target_call = msg_match.group(1).strip()
            raw_msg = msg_match.group(2).strip()
            
            clean_msg = re.sub(r'\{[a-zA-Z0-9]+$', '', raw_msg)
            clean_msg = "".join(c for c in clean_msg if c.isprintable())
            
            self.after(0, self.log_aprs_text_message, src_call, target_call, clean_msg, False)
            
            cot_xml = self.create_cot_chat_xml(src_call, target_call, clean_msg)
            self.send_to_wintak(cot_xml)

        lat, lon = self.parse_aprs_coordinates(payload)
        if lat is not None and lon is not None:
            is_whitelisted = src_call in self.whitelist
            if is_whitelisted or self.map_all_flag:
                cot_type = self.whitelist.get(src_call, "a-f-G-U-C")
                ts = datetime.datetime.now().strftime("%H:%M:%S")
                self.after(0, lambda: self.tree_pos.insert("", 0, values=(ts, src_call, f"{lat:.5f}", f"{lon:.5f}", "SENT")))
                
                cot_xml = self.create_cot_point_xml(src_call, lat, lon, cot_type)
                self.send_to_wintak(cot_xml)

    # --- THREAD 2: LOCAL TCP SERVER FOR WINTAK ---
    def tak_server_loop(self):
        try:
            self.tak_server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tak_server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.tak_server_sock.bind(('127.0.0.1', 8080))
            self.tak_server_sock.listen(1)
            self.after(0, self.log_msg, "[NET] Local TAK Server running on TCP 8080. Waiting for WinTAK...")
        except Exception as e:
            self.after(0, self.log_msg, f"[NET ERROR] Failed to start TAK server: {e}")
            return

        while self.running:
            try:
                self.tak_server_sock.settimeout(1.0)
                conn, addr = self.tak_server_sock.accept()
                self.tak_client_conn = conn
                self.after(0, self.log_msg, f"[NET] WinTAK connected from {addr}!")
                
                # MAGIC FIX 1: Force WinTAK into readable XML mode immediately upon connecting
                conn.sendall(b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n')
                
                # Start the heartbeat to prevent drops
                threading.Thread(target=self.tak_heartbeat_loop, args=(conn,), daemon=True).start()
                
                # Handle incoming messages
                self.handle_wintak_client(conn)
            except socket.timeout:
                continue
            except Exception:
                pass

    def tak_heartbeat_loop(self, conn):
        # MAGIC FIX 2: Send a ping every 20 seconds to reset WinTAK's dead-server timer
        while self.running and self.tak_client_conn == conn:
            try:
                ping_xml = self.create_ping_xml()
                conn.sendall(ping_xml)
                time.sleep(20)
            except:
                break

    def handle_wintak_client(self, conn):
        buffer = ""
        while self.running and self.tak_client_conn == conn:
            try:
                conn.settimeout(1.0)
                data = conn.recv(4096)
                if not data:
                    self.after(0, self.log_msg, "[NET] WinTAK disconnected from local server.")
                    self.tak_client_conn = None
                    break

                if data[0] == 191:
                    continue # Ignore binary protobuf noise if it slips through

                buffer += data.decode('utf-8', errors='ignore')
                
                # TCP Data Buffer: Perfectly reconstructs chopped up chat messages
                while '</event>' in buffer:
                    event_str, buffer = buffer.split('</event>', 1)
                    event_str += '</event>'

                    if '<__chat' in event_str:
                        # Safely extract the chatroom and message even if XML is weirdly formatted
                        cr_match = re.search(r'chatroom="([^"]+)"', event_str)
                        rm_match = re.search(r'<remarks[^>]*>(.*?)</remarks>', event_str)
                        
                        if cr_match and rm_match:
                            target_call = cr_match.group(1)
                            msg_text = rm_match.group(1)
                            
                            clean_target = target_call.replace("APRS-", "").strip()
                            if clean_target and clean_target != "All Chat" and clean_target != self.my_call:
                                self.after(0, self.log_msg, f"[NET] Caught outbound chat directed to {clean_target}")
                                self.transmit_aprs_message(clean_target, msg_text)
            except socket.timeout:
                continue
            except Exception:
                self.tak_client_conn = None
                break

    def send_to_wintak(self, xml_bytes):
        if self.tak_client_conn:
            try:
                self.tak_client_conn.sendall(xml_bytes)
            except Exception as e:
                self.after(0, self.log_msg, f"[NET ERROR] Failed to send to WinTAK: {e}")
                self.tak_client_conn = None

    # --- APRS TRANSMIT ENCODER ---
    def transmit_aprs_message(self, target, message):
        if not self.my_call or not self.kiss_sock: return

        target_padded = target.ljust(9)[:9]
        msg_clipped = message[:67] 
        payload_bytes = f":{target_padded}:{msg_clipped}".encode('ascii')

        frame = bytearray()
        frame.extend(self.encode_ax25_address("APRS", False))
        frame.extend(self.encode_ax25_address(self.my_call, False))
        frame.extend(self.encode_ax25_address("WIDE1-1", False))
        frame.extend(self.encode_ax25_address("WIDE2-1", True))
        frame.extend([0x03, 0xF0])
        frame.extend(payload_bytes)

        kiss_frame = bytearray([0xC0, 0x00])
        for b in frame:
            if b == 0xC0: 
                kiss_frame.extend([0xDB, 0xDC])
            elif b == 0xDB: 
                kiss_frame.extend([0xDB, 0xDD])
            else: 
                kiss_frame.append(b)
        kiss_frame.append(0xC0)

        try:
            self.kiss_sock.sendall(kiss_frame)
            self.after(0, self.log_aprs_text_message, self.my_call, target, msg_clipped, True)
            self.after(0, self.log_msg, f"[RADIO TX PTT] Fired message to {target}")
        except Exception as e:
            self.after(0, self.log_msg, f"[TX ERROR] {e}")

    def encode_ax25_address(self, callsign, is_last):
        parts = callsign.split('-')
        call = parts[0].ljust(6)[:6]
        ssid = int(parts[1]) if len(parts) > 1 else 0

        encoded = bytearray([ord(c) << 1 for c in call])
        ssid_byte = 0x60 | (ssid << 1)
        if is_last: ssid_byte |= 0x01
        encoded.append(ssid_byte)
        return encoded

    def decode_ax25_callsign(self, raw_bytes):
        if len(raw_bytes) < 7: return ""
        call = "".join([chr((b >> 1) & 0x7F) for b in raw_bytes[:6]]).strip()
        ssid = (raw_bytes[6] >> 1) & 0x0F
        return f"{call}-{ssid}" if ssid > 0 else call

    def parse_aprs_coordinates(self, payload_str):
        match = re.search(r'(\d{4}\.\d{2})([NS])[\/\\](\d{5}\.\d{2})([EW])', payload_str)
        if not match: return None, None
        lat_raw, lat_dir, lon_raw, lon_dir = match.groups()
        lat = float(lat_raw[:2]) + (float(lat_raw[2:]) / 60.0)
        if lat_dir == 'S': lat = -lat
        lon = float(lon_raw[:3]) + (float(lon_raw[3:]) / 60.0)
        if lon_dir == 'W': lon = -lon
        return lat, lon

    # --- XML BUILDERS ---
    def create_ping_xml(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        time_fmt = "%Y-%m-%dT%H:%M:%SZ"
        stale = (now + datetime.timedelta(minutes=1)).strftime(time_fmt)
        now_str = now.strftime(time_fmt)
        
        event = f'<event version="2.0" uid="APRS-Bridge-Ping" type="t-x-c-t" time="{now_str}" start="{now_str}" stale="{stale}" how="h-g-i-g-o"><point lat="0.0" lon="0.0" hae="0.0" ce="99" le="99"/><detail/></event>\n'
        return event.encode('utf-8')

    def create_cot_point_xml(self, callsign, lat, lon, cot_type):
        now = datetime.datetime.now(datetime.timezone.utc)
        stale = now + datetime.timedelta(minutes=15)
        time_fmt = "%Y-%m-%dT%H:%M:%SZ"
        
        event = ET.Element("event", {"version": "2.0", "uid": f"APRS-{callsign}", "type": cot_type, "time": now.strftime(time_fmt), "start": now.strftime(time_fmt), "stale": stale.strftime(time_fmt), "how": "m-g"})
        ET.SubElement(event, "point", {"lat": str(lat), "lon": str(lon), "hae": "0.0", "ce": "10.0", "le": "10.0"})
        detail = ET.SubElement(event, "detail")
        ET.SubElement(detail, "contact", {"callsign": callsign})
        ET.SubElement(detail, "color", {"argb": "-16711681"}) 
        
        xml_data = ET.tostring(event, encoding="utf-8").decode("utf-8")
        return (f'{xml_data}\n').encode("utf-8")

    def create_cot_chat_xml(self, sender, target, message):
        now = datetime.datetime.now(datetime.timezone.utc)
        time_fmt = "%Y-%m-%dT%H:%M:%SZ"
        
        contact_uid = f"APRS-{sender}"
        
        event = ET.Element("event", {"version": "2.0", "uid": f"GeoChat.{contact_uid}.{now.timestamp()}", "type": "b-t-f", "time": now.strftime(time_fmt), "start": now.strftime(time_fmt), "stale": (now + datetime.timedelta(minutes=2)).strftime(time_fmt), "how": "m-g"})
        ET.SubElement(event, "point", {"lat": "0.0", "lon": "0.0", "hae": "0.0", "ce": "9999999.0", "le": "9999999.0"})
        detail = ET.SubElement(event, "detail")
        
        chat = ET.SubElement(detail, "__chat", {"parent": "RootContactGroup", "groupOwner": "false", "chatroom": sender, "id": contact_uid, "senderCallsign": sender})
        ET.SubElement(chat, "chatgrp", {"uid0": contact_uid, "uid1": target, "id": contact_uid})
        ET.SubElement(detail, "remarks", {"source": f"BAO.F.ATAK.{contact_uid}", "to": target, "time": now.strftime(time_fmt)}).text = message
        
        xml_data = ET.tostring(event, encoding="utf-8").decode("utf-8")
        return (f'{xml_data}\n').encode("utf-8")

if __name__ == "__main__":
    app = APRSWinTAKApp()
    app.mainloop()
