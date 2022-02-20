#!/usr/bin/python3
import time
import threading
import RPi.GPIO as GPIO # Raspberry Pi GPIO library
import os # enable interfacing with operating system
import subprocess # run new process through operating system
import pyautogui # enable automation of key presses
import wifi_connect # import wifi_connect.py file as a module

GPIO.setwarnings(False) # Ignore Raspberry Pi warnings
GPIO.setmode(GPIO.BOARD) # Use physical pin numbering
GPIO.setup(37, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # Set pin 37 to be an input pin and set initial value to be pulled low (off)

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
# remove all existing bluetooth pairings to avoid issues pairing with device that Raspberry Pi has paired with previously:
paired_devices = (subprocess.getoutput("""sudo bluetoothctl <<EOF 
paired-devices 
EOF""")).split('Device ')[1:] # get names of existing bluetooth pairings

# store IDs of all paired devices in a list
for paired_device in paired_devices:
    devices.append(paired_device[0:17]) # extract substring storing the device ID

# remove all paired devices
for device in devices:
    command = ("""sudo bluetoothctl remove {}""").format(device) # remove each device using its ID
    os.system(command)

def pair():
    # key entries to accept pairing request:
    pyautogui.write("0000")
    pyautogui.press("enter")
    time.sleep(2)
    pyautogui.press("enter")
    pyautogui.press("enter")

    start = time.time()
    while time.time() - start <120: # user has 2 minutes to complete the pairing process
        path = '/home/pi/Desktop/NEA/ComputerScience-NEA-RPi/bluetooth/'
        if len(os.listdir(path)) != 0:  # if file has been received
            wifi_connect.run()  # run module to connect Raspberry Pi to WiFi
            break


# following key strokes are all pressed simultaneously minimise the terminal window opened on boot by @lxterminal to run 'bluetooth_pair.py'
# so that bluetooth pairing dialogue box is at the front of the screen so pyautogui can be used to accept pairing
pyautogui.keyDown("ctrl")
pyautogui.keyDown("alt")
pyautogui.keyDown("d")

pyautogui.keyUp("ctrl")
pyautogui.keyUp("alt")
pyautogui.keyUp("d")

while True:
    if GPIO.input(37) == GPIO.HIGH and threading.active_count() == 1: # when button pressed and pairing process thread not already initiated
        print("Button pressed")
        thread_run = threading.Thread(target=pair) # create pairing thread
        thread_run.start()      
      
# enable automatic acception of files sent from paired/trusted devices
# setup of obexpushd (see open link)
    
    

        
