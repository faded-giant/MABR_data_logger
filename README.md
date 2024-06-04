## Calibrating O2 Sensor

1. Replace ```port="COM8"``` with port number currently assigned to O2 Sensor in ```modbus.py```.
2. Run ``` pip3 install pymodbus```, if necessary in terminal.
3. Run ```python3 modbus.py``` in the directory ```modbus.py``` is located.
4. Script should display ```Raw value: <RAW DEVICE CURRENT> mA, Mapped value: <O2 BASED ON CAL POINTS>%"```
5. Perform a 3 point calibration as follows:
   - For 0% oxygen (```percent_1```), apply pure nitrogen gas to O2 sensor, note raw device current after it is stable.
   - For 10.475% oxygen (```percent_2```), apply a 50% nitrogren gas, 50% Air mixture to O2 sensor, note raw device current after it is stable.
   - For 20.95% oxygen (```percent_3```), apply 100% air to to O2 sensor, note raw device current after it is stable.

6. Replace ```current_1,current_2,current_3``` repectfully with the values noted in previous step.
7. Verify ```Mapped Value``` is as expected for the 3 calibration gases.
8. If all is expected, inside ```config.json```, update the ```current_1,current_2,current_3``` fields in the ```O2_sensor_calibration``` object.
