import json
import os
import time

def run():
    with open('/home/pi/Desktop/NEA/ComputerScience-NEA-RPi/bluetooth/wifi.json', 'r') as file:
        data = json.load(file)
        mySSID = data['ssid']
        passkey = data['psswd']
        
    try: # try except statement required as only needs to kill the wpa_supplicant process if there is one running
        os.system('sudo killall wpa_supplicant')
        time.sleep(5)
    except:
        pass
    
    command = (('wpa_passphrase "{}" "{}" | sudo tee -a /etc/wpa_supplicant/wpa_supplicant.conf').format(mySSID, passkey)) # appends the correctly formatted network data to the configuration file 'wpa_supplicant' so that the raspberry pi can connect to the new wifi connection without overriding the standard wifi connectin procedure
    os.system(command)
    time.sleep(5)
    os.system('sudo wpa_supplicant -B -c /etc/wpa_supplicant/wpa_supplicant.conf -i wlan0')

run()



