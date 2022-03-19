import json
import os
import time
from os.path import join

path = "/home/pi/Desktop/NEA/ComputerScience-NEA-RPi"

def run():
    filePath = join(path, 'bluetooth') # filepath to open 'SmartBell.json' file sent my PC over bluetooth storing wifi connection details
    file = join(filePath,str(os.listdir(filePath)[0]))
    with open(file, 'r') as f:
        data = json.load(f)
        mySSID = data['ssid'] # WiFi network SSID
        passkey = data['psswd'] # WiFi network password
        SmartBellID = data['id'] # unique SmartBell ID
    for file in os.listdir(filePath):
        os.remove(os.path.join(filePath, file))

    newData = {"id": SmartBellID, "training": False} # dictionary storing SmartBell ID sent by user from PC and set 'training' to False (default)

    if os.path.isfile(join(path, 'data.json')) == False: # if the doorbell is being set up for the first time
        with open(join(path,'data.json'), 'w') as jsonFile:
            json.dump(newData, jsonFile) # store SmartBell ID in 'data.json'

    elif SmartBellID != "": # if the user has sent a new SmartBell ID from their PC
        with open(join(path,'data.json'), 'r') as jsonFile:
            data = json.load(jsonFile)
        data['id'] = SmartBellID # assign updated SmartBell ID
        with open(join(path,'data.json'), 'w') as jsonFile:
            json.dump(data, jsonFile)

    if mySSID != '': # if user has sent a new SmartBell ID from their PC
        try: # try except statement required as only needs to kill the wpa_supplicant process if there is one running
            os.system('sudo killall wpa_supplicant') # kills the wpa_supplicant process
            time.sleep(5)
        except:
            pass
        command = (('wpa_passphrase "{}" "{}" | sudo tee -a /etc/wpa_supplicant/wpa_supplicant.conf').format(mySSID, passkey)) # appends the correctly formatted network data to the WiFi configuration file 'wpa_supplicant'
        os.system(command) # execute command through terminal
        time.sleep(5)
        os.system('sudo wpa_supplicant -B -c /etc/wpa_supplicant/wpa_supplicant.conf -i wlan0') # wpa_supplicant automatically selects best network from 'wpa_supplicant.conf' to connect with and runs the WiFi connection process

