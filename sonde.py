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

parser=argparse.ArgumentParser()

parser.add_argument("--sonde_port", help="sonde port",default=None)
args=parser.parse_args()
class Sonde:
        def __init__(self, port):
            self.port = port
            self.disconnected = True
            if port is not None:
                self.disconnected = False
                self.serial_port = serial.Serial(port=args.sonde_port, baudrate=9600, timeout=1)
                self.serial_port.write("0\r\n".encode())
                time.sleep(.1)
        def is_connected(self):
            return not self.disconnected
        def get_value(self):
            serial_data = ""
            if not self.disconnected:
                try:
                    if self.serial_port.in_waiting > 0:
                        serial_data = self.serial_port.readline().decode("utf-8").strip()
                        self.serial_port.flush()
                except:
                    global disconnected_time
                    disconnected_time = datetime.datetime.now()
                    self.disconnected = True
                    return ""
        def get_para(self):
            serial_data = ""
            self.serial_port.write("para \r".encode())
            time.sleep(1)
            if self.serial_port.in_waiting > 0:
                serial_data = self.serial_port.readline().decode("utf-8").strip()
                self.serial_port.flush()

            

            return serial_data
        

sonde = Sonde(args.sonde_port)
print(sonde.is_connected())
while True:
        print(sonde.get_para())
