import paho.mqtt.client as mqtt
import urllib.request as url
from os.path import join
import RPi.GPIO as GPIO # Import Raspberry Pi GPIO library
import os
import json
import time
import threading
import requests

path = "/home/pi/Desktop/NEA/ComputerScience-NEA-RPi"

serverBaseURL = "http://nea-env.eba-6tgviyyc.eu-west-2.elasticbeanstalk.com/"  # base URL to access AWS elastic beanstalk environment

GPIO.setwarnings(False) # Ignore warning for now
GPIO.setmode(GPIO.BOARD) # Use physical pin numbering
GPIO.setup(37, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # Set pin 10 to be an input pin and set initial value to be pulled low (off)

while True:
    if os.path.isfile(join(path, 'data.json')) == False:
        time.sleep(5)
    else:
        with open(join(path,'data.json'), 'r') as jsonFile:
            time.sleep(0.5) # resolves issue with reading file immediately after it is written to (json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0))
            data = json.load(jsonFile)
        if 'accountID' in data:
            accountID = str(data['accountID'])
            break

def on_message(client, userData, msg):
    time_start = time.time()
    print(msg.payload.decode())
    while True: # Run forever
        if GPIO.input(37) == GPIO.HIGH:
            print("Button pressed")
            setupAccount(msg)
            break
        elif time.time() - time_start > 60:
            break
        
        
def setupAccount(msg):    
    with open(join(path,'data.json')) as jsonFile:
        data = json.load(jsonFile)
    SmartBellID = str(data['id'])
    accountID = msg.payload.decode()
    with open(join(path,'data.json'), 'r') as jsonFile:
        data = json.load(jsonFile)
    data['accountID'] = accountID
    with open(join(path,'data.json'), 'w') as jsonFile:
        json.dump(data, jsonFile)
    data_accountID = {"accountID": accountID, 'id': SmartBellID}
    response = requests.post(serverBaseURL + "/update_SmartBellIDs", data_accountID).text
    print(response)
    if response == 'success':
        client.publish(f'pair/{accountID}', 'success')
    elif response == 'error':
        client.publish(f'pair/{accountID}', 'error')
    
def checkID(currentID):
    while True:
        with open(join(path,'data.json')) as jsonFile:
                data = json.load(jsonFile)
        newID = str(data['id'])
        if newID != currentID:
            print('Alteration')
            SmartBellID = newID
            client.unsubscribe(f"id/{currentID}")
            client.subscribe(f"id/{SmartBellID}")
            client.message_callback_add(f"id/{SmartBellID}", on_message)
        time.sleep(5)
        

def on_connect(client, userdata, flags, rc):
    if rc == 0: # if connection is successful
        with open(join(path,'data.json')) as jsonFile:
            data = json.load(jsonFile)
        SmartBellID = str(data['id'])
        client.subscribe(f"id/{SmartBellID}")
        client.message_callback_add(f"id/{SmartBellID}", on_message)
        checkThread = threading.Thread(target=checkID, args = (SmartBellID,))
        checkThread.start()
    else:
        # attempts to reconnect
        client.on_connect = on_connect
        client.username_pw_set(username="yrczhohs", password = "qPSwbxPDQHEI")
        client.connect("hairdresser.cloudmqtt.com", 18973)

 
while True:
    try:
        url.urlopen('http://google.com')
        break
    except:
        time.sleep(5)
        
    
client = mqtt.Client()
client.username_pw_set(username="yrczhohs", password = "qPSwbxPDQHEI")
client.on_connect = on_connect # creates callback for successful connection with broker
client.connect("hairdresser.cloudmqtt.com", 18973) # parameters for broker web address and port number

client.loop_forever()