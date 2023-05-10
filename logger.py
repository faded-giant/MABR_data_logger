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
try:
    disconnected_time = datetime.datetime.now()
    startup=True
    boot_log = True
    button_start = 2
    scale_size = 22
    parser=argparse.ArgumentParser()
    parser.add_argument("--controller_port", help="controller port",default=None)
    parser.add_argument("--O2_port", help="02 sensor port",default=None)
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
            timeout=1
        )
        def is_connected(self):
            return not self.disconnected
        def get_value(self):
            if self.disconnected:
                return -1.0
            try:
                self.client.connect()

                slave_address = 5
                register_address = 7
                number_of_registers = 1

                response = self.client.read_input_registers(register_address, number_of_registers, unit=slave_address)

                if response.isError():
                    print(f"Error in reading register: {response}")
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
                    return f"{mapped_value:.2f}"
            except:
                print("Error in reading register")
                self.disconnected = True
                self.client.close()
                return -1.0

        
    class Controller:
        def __init__(self, port):
            self.port = port
            self.disconnected = True
            if port is not None:
                self.disconnected = False
                self.arduino_serial_port = serial.Serial(port=args.controller_port, baudrate=115200, timeout=1)
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

            self.label = tk.Label(self, text=f"{self.parameter_name}", font=("Arial", scale_size*2))
            self.label.grid(row=row, column=column)

            self.value_label = tk.Label(self, textvariable=self.value, font=("Arial", scale_size*2))
            self.value_label.grid(row=row, column=column+1)

        def update_value(self, new_value):
            self.value.set(new_value)

    o2_sensor = O2_sensor(args.O2_port)
    controller = Controller(args.controller_port)


    class App(tk.Tk):
        def __init__(self):
            super().__init__()
            self.title("Parameter Display GUI")
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

            self.oxygen_display = ParameterDisplay(self, "-", 0, 0)
            self.oxygen_display.grid(row=button_start+7, column=2)
            self.no3_display = ParameterDisplay(self, "NO\u2083:", 1, 0)
            self.no3_display.grid(row=button_start+1, column=2)
            self.DO_display = ParameterDisplay(self, "DO:", 2, 0)
            self.DO_display.grid(row=button_start+2, column=2)
            self.oxygen_display = ParameterDisplay(self, "-", 3, 0)
            self.oxygen_display.grid(row=button_start+3, column=2)
            self.oxygen_display = ParameterDisplay(self, "-", 4, 0)
            self.oxygen_display.grid(row=button_start+4, column=2)
            self.oxygen_display = ParameterDisplay(self, "-", 5, 0)
            self.oxygen_display.grid(row=button_start+5, column=2)
            self.oxygen_display = ParameterDisplay(self, "-", 6, 0)
            self.oxygen_display.grid(row=button_start+6, column=2)
            self.oxygen_display = ParameterDisplay(self, "O\u2082:", 7, 0)
            self.oxygen_display.grid(row=button_start, column=2)

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
                controller.arduino_serial_port.close()
            except:
                pass
            self.destroy()

        def update_values(self):
            oxygen_value = ""
            global previous_arduino_log_entry
            arduino_data=""
            try:
                arduino_data = controller.get_value()
                oxygen_value = o2_sensor.get_value()
                self.oxygen_display.update_value(f"{oxygen_value}%")
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
                if arduino_data != previous_arduino_log_entry or boot_log or current_time - self.last_logged_time >= logging_period:
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
            controller_log_entry = ""
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
                controller_log_entry += desired_text + ", "
    
    
        def send_string(self, command, entry):
            digits = entry.get()
            string_to_send = f"{command}{digits}\n"
            controller.arduino_serial_port.write(string_to_send.encode())

        def log_data(self, oxygen_value):
            # Log the data to a file
            today = datetime.date.today()
            date_str = today.strftime('%Y-%b-%d')
            log_file_name = f"../MABR_data/{date_str}.csv"
            new_day = False
            if not os.path.exists(log_file_name):
                new_day = True
            with open(log_file_name, 'a') as log_file:
                if new_day:
                    # If the log file is new, write an initial log message
                    initial_log_message = "Timestamp,O\u2082(%),V01,V02,V03,B1,B2,B3,V04,V05,V06,V07\n"
                    log_file.write(f"{initial_log_message}\n")
                log_file.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}, {oxygen_value}, {controller_log_entry}\n")
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
                try:
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
    # The rest of your existing code goes here


    # The rest of your existing code goes here

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
        app.mainloop()
except Exception as e:
    traceback.print_exc()


    