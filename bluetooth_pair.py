#!/usr/bin/python3
import time
import RPi.GPIO as GPIO # Import Raspberry Pi GPIO library
import os
import wifi_connect
import pyautogui
import subprocess
import threading

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BOARD) # use physical pin numbering
GPIO.setup(37, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # set pin 37 to be an input pin and set initial value to be pulled low (off)


if os.path.isfile('/home/pi/Desktop/NEA/ComputerScience-NEA-RPi/bluetooth/SmartBell.json') == True:
    os.remove('/home/pi/Desktop/NEA/ComputerScience-NEA-RPi/bluetooth/SmartBell.json')

# make Raspberry Pi discoverable on boot.
os.system("""sudo bluetoothctl <<EOF
power on
discoverable on
pairable on
EOF
""")

devices = []
paired_devices = (subprocess.getoutput("""sudo bluetoothctl <<EOF
paired-devices
EOF""")).split('Device ')[1:] # list of paired devices

for paired_device in paired_devices: # iterate through paired devices
    devices.append(paired_device[0:17]) # create list with addresses of paired devices
        
for device in devices: # iterate through paired devices and remove pairing
    command = ("""sudo bluetoothctl remove {}""").format(device) # remove device pairing
    os.system(command)
    
def pair():
    # pair Raspberry Pi with PC over bluetooth
    pyautogui.write("0000") # pairing code
    pyautogui.press("enter") # press enter key
    time.sleep(2)
    pyautogui.press("enter")
    pyautogui.press("enter")
    start = time.time()
    while time.time() - start <120:
        path = '/home/pi/Desktop/NEA/ComputerScience-NEA-RPi/bluetooth/'
        if len(os.listdir(path)) != 0: # check if file with wifi details received by Raspberry Pi
            wifi_connect.run() # connect to WiFi
            break


pyautogui.keyDown("ctrl")
pyautogui.keyDown("alt")
pyautogui.keyDown("d")

pyautogui.keyUp("ctrl")
pyautogui.keyUp("alt")
pyautogui.keyUp("d")

while True:
    if GPIO.input(37) == GPIO.HIGH and threading.active_count() == 1: # if 'pair' button pressed AND Raspberry Pi not currently pairing with a device
        thread_run = threading.Thread(target =pair)
        thread_run.start()      
      
      
    
    

        
