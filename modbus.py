from pymodbus.client.sync import ModbusSerialClient
from functools import partial
import tkinter as tk
import sys
import time
import serial
import re
# Calibration points
input_max = 20
current_3 = 8.34
percent_3 = 20.95
current_2 = 5.425 
percent_2 = 10.475
current_1 = 1.592
percent_1 = 0
output_max = 25
scale_size = 22
button_start = 2
startup=True



arduino_serial_port = serial.Serial(port=sys.argv[2], baudrate=115200, timeout=1)

def map_value(value, input_min, input_max, output_min, output_max):
    return output_min + (value - input_min) * (output_max - output_min) / (input_max - input_min)

client = ModbusSerialClient(
    method="rtu",
    port=sys.argv[1],  # Replace with your COM port
    baudrate=9600,
    bytesize=8,
    parity="N",
    stopbits=1,
    timeout=1
)


def get_oxygen_value():
    
    client.connect()

    slave_address = 5
    register_address = 7
    number_of_registers = 1

    response = client.read_input_registers(register_address, number_of_registers, unit=slave_address)

    if response.isError():
        print(f"Error in reading register: {response}")
    else:
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
        client.close()
        return f"{mapped_value:.2f}"

    
    



def read_arduino_data(serial_port):
    serial_data = ""
    while True:
        try:
            serial_data = serial_port.readline().decode("utf-8").strip()
            break
        except UnicodeDecodeError:
            pass

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
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Parameter Display GUI")
        self.attributes("-fullscreen", True)
        self.geometry("{0}x{1}+0+0".format(self.winfo_screenwidth(), self.winfo_screenheight()))
        #self.grid_rowconfigure(0, weight=1)
        #for i in range(1, 6):
            #self.grid_rowconfigure(i, weight=0)
        self.close_button = tk.Button(self, text="Close", font=("Arial", 14), command=self.close_app)
        self.close_button.grid(row=0, column=6, columnspan=6)

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_columnconfigure(2, weight=1)
        self.grid_columnconfigure(3, weight=0)
        self.grid_columnconfigure(4, weight=1)  # Add this line
        self.grid_columnconfigure(5, weight=0)  # Add this line

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
        for i in range(11):
            indicator = tk.Label(self,font=("Arial", scale_size*2))
            indicator.grid(row=i+1, column=3,sticky="w")
            self.indicators.append(indicator)


        self.logging_period_label = tk.Label(self, text="Logging Period (s):", font=("Arial", scale_size))
        self.logging_period_label.grid(row=1, column=0,sticky="e")

        self.logging_period_entry = tk.Entry(self, font=("Arial", scale_size),width=4)
        self.logging_period_entry.grid(row=1, column=1 )
        self.logging_period_entry.insert(0, "1")  # Default logging period of 1 second

        self.last_logged_time = time.time()

        commands = ["U41", "U42", "U51", "U52", "U61", "U62", "U71", "U72"]

        self.entries = [[None for _ in range(2)] for _ in range(4)]

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
                entry_label = tk.Label(self, text=f"V0" + str(valveNumber) + setpoint + " (s)", font=("Arial", scale_size))
                entry_label.grid(row=i*2 +j +button_start , column=0,sticky="e")

                entry_widget = tk.Entry(self, font=("Arial", scale_size), width=5)
                entry_widget.grid(row=i*2 +j +button_start, column=1)
                entry_widget.insert(0, i)

                self.entries[i][j] = entry_widget

                send_button = tk.Button(self, text=f"Update", font=("Arial", scale_size),
                                        command=partial(self.send_string, command, entry_widget))
                send_button.grid(row=i*2 +j +button_start, column=2,sticky="w")

        self.update_values()

    # The rest of your existing App class code goes here


    # The rest of
    def close_app(self):
        arduino_serial_port.close()
        self.destroy()

    def update_values(self):
        oxygen_value = ""
        arduino_data=""
        try:
            arduino_data = read_arduino_data(arduino_serial_port)
            oxygen_value = get_oxygen_value()
            self.oxygen_display.update_value(f"{oxygen_value}%")


            self.update_arduino_fields(arduino_data)
            print(f"Arduino data: {arduino_data}")

            current_time = time.time()
            try:
                logging_period = float(self.logging_period_entry.get())
            except ValueError:
                logging_period = 1.0

            if current_time - self.last_logged_time >= logging_period:
                self.log_data(oxygen_value)
                self.last_logged_time = current_time
            self.update_indicators(arduino_data[1:11])
        except serial.serialutil.SerialException as e:
            print(f"Serial exception: {e}")
            arduino_serial_port.close()
            self.destroy()
            return
        except Exception as e:
            print(f"Unexpected exception: {e}")
            arduino_serial_port.close()
            self.destroy()
            return
        self.after(1, self.update_values)

    # The rest of your existing App class code goes here
    def update_indicators(self, status_bits):
        on_text = ""
        off_text = ""

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
   
   
    def send_string(self, command, entry):
        digits = entry.get()
        string_to_send = f"{command}{digits}\n"
        print (string_to_send)
        arduino_serial_port.write(string_to_send.encode())
    def log_data(self, oxygen_value):
        # Log the data to a file
        with open("data_log.txt", "a") as log_file:
            log_file.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - O\u2082: {oxygen_value}%\n")
    def update_arduino_fields(self, arduino_data):
        arduino_data = arduino_data.strip()  # Remove any whitespace or newline characters
        global startup
        if arduino_data.startswith('#') and startup:
            startup=False
            hex_values = re.findall('[0-9A-Fa-f]{4}', arduino_data[11:])  # Extract 4-digit hex values
            print(f"Hex values: {hex_values}")
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
            print(f"Hex values: {hex_values}")
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
# The rest of your existing code goes here


# The rest of your existing code goes here

if __name__ == "__main__":
    app = App()
    app.mainloop()


# The rest of your existing code goes here

# Make sure to close the serial port when the application is closed
def on_closing():
    arduino_serial_port.close()
    app.destroy()

app.protocol("WM_DELETE_WINDOW", on_closing)