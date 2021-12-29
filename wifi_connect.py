import json
import os
import time
from os.path import join

path = "/home/pi/Desktop/NEA/ComputerScience-NEA-RPi"


def run():
    with open('/home/pi/Desktop/NEA/ComputerScience-NEA-RPi/bluetooth/SmartBell.json', 'r') as file:
        data = json.load(file)
        mySSID = data['ssid']
        passkey = data['psswd']
        SmartBellID = data['id']
        
        newData = {"id": SmartBellID}
        if os.path.isfile(join(path, 'data.json')) == False:
            with open(join(path,'data.json'), 'w') as jsonFile:
                json.dump(newData, jsonFile)
        elif SmartBellID != "":
            with open(join(path,'data.json'), 'r') as jsonFile:
                data = json.load(jsonFile)
            data['id'] = SmartBellID
            with open(join(path,'data.json'), 'w') as jsonFile:
                json.dump(data, jsonFile)
                
            
    if mySSID != '':    
        try: # try except statement required as only needs to kill the wpa_supplicant process if there is one running
            os.system('sudo killall wpa_supplicant')
            time.sleep(5)
        except:
            pass
        
        command = (('wpa_passphrase "{}" "{}" | sudo tee -a /etc/wpa_supplicant/wpa_supplicant.conf').format(mySSID, passkey)) # appends the correctly formatted network data to the configuration file 'wpa_supplicant' so that the raspberry pi can connect to the new wifi connection without overriding the standard wifi connectin procedure
        os.system(command)
        time.sleep(5)
        os.system('sudo wpa_supplicant -B -c /etc/wpa_supplicant/wpa_supplicant.conf -i wlan0')



