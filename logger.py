from pymodbus.client.sync import ModbusSerialClient
from functools import partial
import tkinter as tk
import sys, os
import time
import serial
import re
import datetime
import json
import argparse, sys
import traceback
import threading
from opcua import ua, Server
# para output:#:start  18:pH 19:ORP(mv) 48:NH4 (mg/L) 106:NO3 mg/L 212: ODO mg/L 1: Temp 5:Conduct
log_buffer = ["-", "-", "-", "-", "-", "-","-","-","-","-","-","-","-","-","-","-","-","-","-","-","-"]
pH_idx = 1
orp_idx = 2
NH4_idx = 3
NO3_idx = 4
ODO_idx = 5
temp_idx = 6
cond_idx = 7
sonde_log_entry = ""
o2_mA = ""
try:
    disconnected_time = datetime.datetime.now()
    startup=True
    boot_log = True
    button_start = 2
    scale_size = 18
    parser=argparse.ArgumentParser()
    parser.add_argument("--controller_port", help="controller port",default=None)
    parser.add_argument("--O2_port", help="02 sensor port",default=None)
    parser.add_argument("--sonde_port", help="sonde port",default=None)
    args=parser.parse_args()
    previous_arduino_log_entry = ""
    controller_log_entry = ""
    def read_config_file(file_path):
        with open(file_path, 'r') as file:
            config = json.load(file)
        return config

    def write_config_file(file_path, config):
        with open(file_path, 'w') as file:
            json.dump(config, file, indent=2)

    config_file_path = 'config.json'
    config = read_config_file(config_file_path)

    # Access the values from the config

    def map_value(value, input_min, input_max, output_min, output_max):
        return output_min + (value - input_min) * (output_max - output_min) / (input_max - input_min)


    class Sonde:
        def __init__(self, port):
            self.port = port
            self.disconnected = True
            self.serial_data = ""
            if port is not None:
                self.disconnected = False
                self.serial_port = serial.Serial(port=port, baudrate=9600, timeout=1) 
                #self.serial_port.write("run \r".encode())
                self.reader_thread = threading.Thread(target=self.read_from_port)
                self.reader_thread.daemon = True  # Ensure thread closes when main program closes
                self.reader_thread.start()

        def is_connected(self):
            return not self.disconnected

        def get_value(self):
            return self.serial_data

        def read_from_port(self):
            while not self.disconnected:
                try:
                    if self.serial_port.in_waiting > 0:
                        self.serial_data = self.serial_port.readline().decode("utf-8").strip()
                        self.serial_port.flush()
                except:
                    global disconnected_time
                    disconnected_time = datetime.datetime.now()
                    self.disconnected = True

    class O2_sensor:
        def __init__(self, port):
            self.calibration = config['O2_sensor_calibration']
            self.port = port
            self.disconnected = True
            if port is not None:
                self.disconnected = False
                self.client = ModbusSerialClient(
            method="rtu",
            port=args.O2_port,  # Replace with your COM port
            baudrate=9600,
            bytesize=8,
            parity="N",
            stopbits=1,
            timeout=.2
        )
            self.oxygen_value = -1.0
            self.reader_thread = threading.Thread(target=self.loop)
            self.reader_thread.daemon = True  # Ensure thread closes when main program closes
            self.reader_thread.start()
        def is_connected(self):
            return not self.disconnected
        def get_value(self):
        	return self.oxygen_value
        def loop(self):
            while True:
                self.get_data()
        def get_data(self):
            try:
                self.client.connect()
                slave_address = 5
                register_address = 7
                number_of_registers = 1

                response = self.client.read_input_registers(register_address, number_of_registers, unit=slave_address)

                if response.isError():
                    print(f"Error in reading register: {response}")
                    self.oxygen_value = "ERR"
                else:
                    current_3 = self.calibration['current_3']
                    percent_3 = self.calibration['percent_3']
                    current_2 = self.calibration['current_2']
                    percent_2 = self.calibration['percent_2']
                    current_1 = self.calibration['current_1']
                    percent_1 = self.calibration['percent_1']
                    input_max = self.calibration['input_max']
                    output_max = self.calibration['output_max']

                    measuring_value_channel_1 = response.registers[0] *.001
                    global o2_mA
                    o2_mA = measuring_value_channel_1
                    if measuring_value_channel_1 >= current_3:
                        mapped_value = map_value(measuring_value_channel_1, current_3, input_max, percent_3, output_max)
                    elif measuring_value_channel_1 >= current_2:
                        mapped_value = map_value(measuring_value_channel_1, current_2, current_3, percent_2, percent_3)
                    else:
                        mapped_value = map_value(measuring_value_channel_1, current_1, current_2, percent_1, percent_2)

                # Linear extrapolation beyond the last calibration point
                    if measuring_value_channel_1 > current_3:
                        slope = (percent_3 - percent_2) / (current_3 - current_2)
                        intercept = percent_3 - slope * current_3
                        mapped_value = slope * measuring_value_channel_1 + intercept

                #print(f"Raw value: {measuring_value_channel_1} mA, Mapped value: {mapped_value}%")
                    self.client.close()
                    self.oxygen_value = f"{mapped_value:.2f}"
            except:
                print("Error in reading register")
                self.disconnected = True
                self.client.close()
                self.oxygen_value = "ERR"

        
    class Controller:
        def __init__(self, port):
            self.port = port
            self.disconnected = True
            if port is not None:
                self.disconnected = False
                self.arduino_serial_port = serial.Serial(port=args.controller_port, baudrate=115200, timeout=.1)
        def is_connected(self):
            return not self.disconnected
        def get_value(self):
            serial_data = ""
            if not self.disconnected:
                try:
                    serial_data = self.arduino_serial_port.readline().decode("utf-8").strip()
                except:
                    global disconnected_time
                    disconnected_time = datetime.datetime.now()
                    self.disconnected = True
                    return ""

            return serial_data
        
    class ParameterDisplay(tk.Frame):
        def __init__(self, parent, parameter_name, row, column, *args, **kwargs):
            super().__init__(parent, *args, **kwargs)
            self.parameter_name = parameter_name
            self.value = tk.StringVar()

            self.label = tk.Label(self, text=f"{self.parameter_name}", font=("Arial", scale_size))
            self.label.grid(row=row, column=column)

            self.value_label = tk.Label(self, textvariable=self.value, font=("Arial", scale_size))
            self.value_label.grid(row=row, column=column+1)

        def update_value(self, new_value):
            self.value.set(new_value)

    o2_sensor = O2_sensor(args.O2_port)
    controller = Controller(args.controller_port)
    sonde = Sonde(args.sonde_port)

    class App(tk.Tk):
        def __init__(self):
            super().__init__()
            self.server = Server()
            self.server.set_endpoint("opc.tcp://localhost:4841/opc/")
            self.server.set_server_name("MABR")
            self.uri = "http://examples.freeopcua.github.io"
            self.idx = self.server.register_namespace(self.uri)
            self.objects = self.server.get_objects_node()

            # populating our address space
            self.opc_data = self.objects.add_object(self.idx, "MABR_DATA")
            self.opc_pressure = self.opc_data.add_variable(self.idx, "pressure", -1.0)
            self.opc_pressure.set_writable()    # Set MyVariable to be writable by clients
            self.attributes("-fullscreen", True)
            self.geometry("{0}x{1}+0+0".format(self.winfo_screenwidth(), self.winfo_screenheight()))
            #self.grid_rowconfigure(0, weight=1)
            #for i in range(1, 6):
                #self.grid_rowconfigure(i, weight=0)
            self.close_button = tk.Button(self, text="Close", font=("Arial", 14), command=on_closing)
            self.close_button.grid(row=0, column=6, columnspan=6)

            self.grid_columnconfigure(0, weight=1)
            self.grid_columnconfigure(1, weight=0)
            self.grid_columnconfigure(2, weight=1)
            self.grid_columnconfigure(3, weight=0)
            self.grid_columnconfigure(4, weight=1)  # Add this line
            self.grid_columnconfigure(5, weight=0)  # Add this line
            self.status_label = tk.Label(self, text="Status: Initializing...", font=("Arial", 14))
            self.status_label.grid(row=0, column=0, columnspan=6, sticky="w")
            
            self.spare2 = ParameterDisplay(self, "Temp (C):", 0, 0)
            self.spare2.grid(row=button_start+7, column=2)
            self.no3_display = ParameterDisplay(self, "NO\u2083 (mg/L):", 1, 0)
            self.no3_display.grid(row=button_start+1, column=2)
            self.DO_display = ParameterDisplay(self, "ODO(mg/L):", 2, 0)
            self.DO_display.grid(row=button_start+2, column=2)
            self.ph_display = ParameterDisplay(self, "pH:", 3, 0)
            self.ph_display.grid(row=button_start+3, column=2)
            self.no4_display = ParameterDisplay(self, "NH\u2084 (mg/L):", 4, 0)
            self.no4_display.grid(row=button_start+4, column=2)
            self.orp_display = ParameterDisplay(self, "ORP (mV):", 5, 0)
            self.orp_display.grid(row=button_start+5, column=2)
            self.spare1_dis = ParameterDisplay(self, "Press (psi):", 6, 0)
            self.spare1_dis.grid(row=button_start+6, column=2)
            self.oxygen_display = ParameterDisplay(self, "O\u2082:", 7, 0)
            self.oxygen_display.grid(row=button_start, column=2)
            self.flow_display = ParameterDisplay(self, "Flow (gpm):", 8, 0)
            self.flow_display.grid(row=button_start+8, column=2)
            self.flow_temp_display = ParameterDisplay(self, "Flow Temp (C):", 8, 0)
            self.flow_temp_display.grid(row=button_start+9, column=2)
            self.server.start()
            self.indicators = []
            try:
                for i in range(11):
                    indicator = tk.Label(self,font=("Arial", scale_size*2))
                    indicator.grid(row=i+1, column=3,sticky="w")
                    self.indicators.append(indicator)
            except:
                print("Error in creating indicators")


            self.logging_period_label = tk.Label(self, text="Logging Period (s):", font=("Arial", scale_size))
            self.logging_period_label.grid(row=1, column=0,sticky="e")

            self.logging_period_entry = tk.Entry(self, font=("Arial", scale_size),width=4)
            self.logging_period_entry.grid(row=1, column=1 )
            self.logging_period_entry.insert(0, config['logging_period'])  # Default logging period of 1 second

            self.last_logged_time = time.time()

            commands = ["U41", "U42", "U51", "U52", "U61", "U62", "U71", "U72"]

            self.entries = [[None for _ in range(2)] for _ in range(4)]
            try:
                for i in range(4):
                    for j in range(2):
                        command = commands[i * 2 + j]
                        valveNumber = i + 4
                        setpoint = ""
                        if i < 2 and j == 0:
                            setpoint = " CW"
                        elif i < 2 and j == 1:
                            setpoint = " CCW"
                        elif j == 0:
                            setpoint = " ON"
                        elif j == 1:
                            setpoint = " OFF"
                        state = f"V0" + str(valveNumber) + setpoint
                        entry_label = tk.Label(self, text= state+" (s)", font=("Arial", scale_size))
                        entry_label.grid(row=i*2 +j +button_start , column=0,sticky="e")
                        entry_widget = tk.Entry(self, font=("Arial", scale_size), width=5)
                        entry_widget.grid(row=i*2 +j +button_start, column=1)
                        entry_widget.insert(0, i)

                        self.entries[i][j] = entry_widget

                        send_button = tk.Button(self, text=f"Update", font=("Arial", scale_size),
                                                command=partial(self.send_string, command, entry_widget))
                        send_button.grid(row=i*2 +j +button_start, column=2,sticky="w")
            except:
                print("Error in creating entries")
            try:
                for i in range(4):
                    send_button = tk.Button(self, text=f"Toggle", font=("Arial", scale_size),
                                                command=partial(self.send_string, "U" + str(i+4)+"3",entry_widget))
                    send_button.grid(row=i +7, column=4,sticky="w")
            except:
                print("Error in creating toggle buttons")


            self.update_values()

        # The rest of your existing App class code goes here

        def update_status(self, status_text):
            self.status_label.config(text=f"Status: {status_text}")
        # The rest of
        def close_app(self):
            try:
                self.server.stop()
                controller.arduino_serial_port.close()
            except:
                pass
            self.destroy()

        def update_values(self):
            oxygen_value = ""
            global previous_arduino_log_entry
            global sonde_log_entry
            arduino_data=""
            try:
                arduino_data = controller.get_value()
                oxygen_value = o2_sensor.get_value()
                sonde_data = sonde.get_value()
                sonde_data = sonde_data.split(" ")
                #print(sonde_data)
                sonde_log_entry = ','.join(sonde_data[1:])
                
                if sonde_data[0] == "#":
                    self.ph_display.update_value(sonde_data[pH_idx])
                    self.orp_display.update_value(sonde_data[orp_idx])
                    self.no4_display.update_value(sonde_data[NH4_idx])
                    self.no3_display.update_value(sonde_data[NO3_idx])
                    self.DO_display.update_value(sonde_data[ODO_idx])
                    self.spare2.update_value(sonde_data[temp_idx])
                    log_buffer[11] = sonde_data[pH_idx]
                    log_buffer[12] = sonde_data[orp_idx]
                    log_buffer[13] = sonde_data[NH4_idx]
                    log_buffer[14] = sonde_data[NO3_idx]
                    log_buffer[15] = sonde_data[ODO_idx]
                    log_buffer[17] = sonde_data[temp_idx]
                    log_buffer[18] = sonde_data[cond_idx]
                self.oxygen_display.update_value(f"{oxygen_value}% ({o2_mA} mA)")
                log_buffer[0] = str(oxygen_value)
                self.update_status("Running")
                if not controller.is_connected()and config["controller_enabled"]:
                    current_time = datetime.datetime.now()
                    time_difference = current_time - disconnected_time
                    seconds_since_event = time_difference.total_seconds()
                    countdown = config['restart_delay'] - seconds_since_event
                    status_text = f"Controller is disconnected. Restarting in {countdown:.0f} seconds"
                    if countdown <= 0:
                        self.close_app()
                        return
                    self.update_status(status_text)
                if not o2_sensor.is_connected() and config["o2_sensor_enabled"]:
                    current_time = datetime.datetime.now()
                    time_difference = current_time - disconnected_time
                    seconds_since_event = time_difference.total_seconds()
                    countdown = config['restart_delay'] - seconds_since_event
                    status_text = f"O2 Sensor is disconnected. Restarting in {countdown:.0f} seconds"
                    if countdown <= 0:
                        self.close_app()
                        return
                    self.update_status(status_text)
                self.update_arduino_fields(arduino_data)
                current_time = time.time()
                try:
                    logging_period = float(self.logging_period_entry.get())
                except ValueError:
                    logging_period = 1.0
                global boot_log
                if boot_log or current_time - self.last_logged_time >= logging_period:
                    boot_log = False
                    self.log_data(oxygen_value)
                    self.last_logged_time = current_time
                previous_arduino_log_entry = arduino_data
                self.update_indicators(arduino_data[1:11])
            except serial.serialutil.SerialException as e:
                pass
            except Exception as e:
                pass
            self.after(1, self.update_values)

        # The rest of your existing App class code goes here
        def update_indicators(self, status_bits):
            on_text = ""
            off_text = ""
            global controller_log_entry
            global sonde_log_entry
            controller_log_entry =""
            if controller.disconnected:
                 for i in range(1,11):
                    log_buffer[i] = "-"
            for i, bit in enumerate(status_bits):
                if i <= 2:
                
                    on_text = "V0"+str(i+1)+" :CW"
                    off_text = "V0"+str(i+1)+" :CCW"
                elif i < 6:
                    on_text = "B"+str(i-2)+" :HIGH"
                    off_text = "B"+str(i-2)+" :LOW"
                elif i < 8:
                    on_text = "V0"+str(i-2)+" :CW"
                    off_text = "V0"+str(i-2)+" :CCW"
                else:
                    on_text = "V0"+str(i-2)+" :ON"
                    off_text = "V0"+str(i-2)+" :OFF"
                if bit == '1':
                    self.indicators[i].config(text=on_text)
                elif bit == '0':
                    self.indicators[i].config(text=off_text)
                indicator_text = self.indicators[i].cget("text")
                parts = indicator_text.split(":")
                desired_text = parts[1].strip()
                log_buffer[i+1] = desired_text
    
    
        def send_string(self, command, entry):
            digits = entry.get()
            string_to_send = f"{command}{digits}\n"
            controller.arduino_serial_port.write(string_to_send.encode())

        def log_data(self, oxygen_value):
            # Log the data to a file
            today = datetime.date.today()
            global sonde_log_entry
            date_str = today.strftime('%Y-%b-%d')
            log_file_name = f"/home/cee/Dropbox/MABR_data/{date_str}.csv"
            new_day = False
           
            if not os.path.exists(log_file_name):
                new_day = True
            with open(log_file_name, 'a') as log_file:
                if new_day:
                    # If the log file is new, write an initial log message
                    initial_log_message = "Timestamp,O\u2082(%),V01,V02,V03,B1,B2,B3,V04,V05,V06,V07,pH,ORP (mV),NO\u2084 (mg/L),NO\u2083 (mg/L),ODO(mg/L),Pressure  (psi),Temp(C),Cond(uS/cm),Flow (gpm),Flow Temp (C)\n"
                    print(initial_log_message)
                    log_file.write(f"{initial_log_message}\n")
                global log_buffer
                uid = int(os.environ.get('SUDO_UID'))
                gid = int(os.environ.get('SUDO_GID'))
                os.chown(log_file_name,uid,gid)
                log_file.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}, {','.join(log_buffer)}\n")
        def update_arduino_fields(self, arduino_data):
            arduino_data = arduino_data.strip()  # Remove any whitespace or newline characters
            global startup
            if arduino_data.startswith('#') and startup:
                startup=False
                hex_values = re.findall('[0-9A-Fa-f]{4}', arduino_data[11:])  # Extract 4-digit hex values
        
                for i in range(len(hex_values)):
                    row = i // 2
                    col = i % 2
                    if row < len(self.entries) and col < len(self.entries[row]):
                        entry_widget = self.entries[row][col]
                        entry_widget.delete(0, tk.END)
                        decimal_value = int(hex_values[i], 16)
                        current_value = entry_widget.get()
                        if current_value != str(decimal_value):
                            entry_widget.delete(0, tk.END)
                            entry_widget.insert(0, decimal_value)
            if arduino_data.startswith('#'):
                startup=False
                hex_values = re.findall('[0-9A-Fa-f]{4}', arduino_data[11:])  # Extract 4-digit hex values
                pressure = (int(hex_values[8],16)/1024)*config['press_sensor_cal']['slope']+config['press_sensor_cal']['y_intercept']
                flow = (int(hex_values[9],16)/1024*5)*config['flow_sensor_cal']['slope']+config['flow_sensor_cal']['y_intercept']
                flow_temp = (int(hex_values[10],16)/1024*5)*config['flow_temp_sensor_cal']['slope']+config['flow_temp_sensor_cal']['y_intercept']
                log_buffer[16]=str(round(pressure,2))
                log_buffer[19]=str(round(flow,2))
                log_buffer[20]=str(round(flow_temp,2))
                self.opc_pressure.set_value(round(pressure,2))
                try:
                    self.spare1_dis.update_value(str(round(pressure,2))+ " (" + str(round(int(hex_values[8],16)/1024,2)) + " V)")
                    self.flow_display.update_value(str(round(flow,2))+ " (" + str(round(int(hex_values[9],16)/1024*5,2)) + " V)")
                    self.flow_temp_display.update_value(str(round(flow_temp,2))+ " (" + str(round(int(hex_values[10],16)/1024*5,2)) + " V)")
                    for i in range(len(hex_values)):
                        row = i // 2
                        col = i % 2
                        if row < len(self.entries) and col < len(self.entries[row]):
                            entry_widget = self.entries[row][col]
                            decimal_value = int(hex_values[i], 16)
                            current_value = entry_widget.get()
                            if current_value != str(decimal_value):
                                # Set the background color to red if the hex value doesn't match
                                entry_widget.config(bg="red")
                            else:
                                # Set the background color to green if the hex value matches
                                entry_widget.config(bg="green")
                except:
                    pass
    

    def on_closing():
        try:
            controller.arduino_serial_port.close()
        except:
            pass
        app.destroy()

    time.sleep(2)
    if __name__ == "__main__":
        app = App()
        app.protocol("WM_DELETE_WINDOW", on_closing)
        try:
            app.mainloop()
        finally:
            app.server.stop()
except Exception as e:
    traceback.print_exc()


    
