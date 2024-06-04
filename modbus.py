from pymodbus.client.sync import ModbusSerialClient

# Calibration points
input_max = 20
current_3 = 8.34
percent_3 = 20.95
current_2 = 5.425 
percent_2 = 10.475
current_1 = 1.592
percent_1 = 0
output_max = 25

def map_value(value, input_min, input_max, output_min, output_max):
    return output_min + (value - input_min) * (output_max - output_min) / (input_max - input_min)

client = ModbusSerialClient(
    method="rtu",
    port="COM8",  # Replace with your COM port
    baudrate=9600,
    bytesize=8,
    parity="N",
    stopbits=1,
    timeout=1
)

while True:
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

        print(f"Raw value: {measuring_value_channel_1} mA, Mapped value: {mapped_value}%")

    client.close()