#!/usr/bin/python3
import time
import RPi.GPIO as GPIO # Import Raspberry Pi GPIO library
import os
import wifi_connect
import pyautogui
import subprocess
import threading

GPIO.setwarnings(False) # Ignore warning for now
GPIO.setmode(GPIO.BOARD) # Use physical pin numbering
GPIO.setup(37, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # Set pin 10 to be an input pin and set initial value to be pulled low (off)


if os.path.isfile('/home/pi/Desktop/NEA/ComputerScience-NEA-RPi/bluetooth/wifi.json') == True:
    os.remove('/home/pi/Desktop/NEA/ComputerScience-NEA-RPi/bluetooth/wifi.json')

devices = []
paired_devices = (subprocess.getoutput("""sudo bluetoothctl <<EOF
paired-devices
EOF""")).split('Device ')[1:]

for paired_device in paired_devices:
    devices.append(paired_device[0:17])
        
for device in devices:
    command = ("""sudo bluetoothctl remove {}""").format(device)
    print(command)
    os.system(command)
    
def pair():
    os.system("""sudo bluetoothctl <<EOF
    power on
    discoverable on
    pairable on
    default-agent
    """)
                   

    start = time.time()
    while time.time() - start <120:
        pyautogui.press("tab")
        pyautogui.press("enter")
        time.sleep(5)
        if os.path.isfile('/home/pi/Desktop/NEA/ComputerScience-NEA-RPi/bluetooth/wifi.json') == True:
            wifi_connect.run()
            break
        
pyautogui.keyDown("ctrl")
pyautogui.keyDown("alt")
pyautogui.keyDown("d")

pyautogui.keyUp("ctrl")
pyautogui.keyUp("alt")
pyautogui.keyUp("d")

while True: # Run forever
    if GPIO.input(37) == GPIO.HIGH and threading.active_count() == 1:
        print("Button pressed")
        thread_run = threading.Thread(target =pair)
        thread_run.start()      
  
    
    

        
