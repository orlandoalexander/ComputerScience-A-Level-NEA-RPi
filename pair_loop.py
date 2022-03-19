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

GPIO.setwarnings(False) 
GPIO.setmode(GPIO.BOARD) # use physical pin numbering
GPIO.setup(37, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # set pin 37 to be an input pin and set initial value to be pulled low (off)

while True: # block program until user set up doorbell
    if os.path.isfile(join(path, 'data.json')) == False: # check if user has already set up doorbell 
        time.sleep(5)
    else:
        break

def on_message(client, userData, msg):
    # callback function called when pairing request received
    time_start = time.time()
    while True: 
        if GPIO.input(37) == GPIO.HIGH: # check if user pressed 'pair' button on doorbell
            connectDoorbell(msg) # pair doorbell with user account  
            break
        elif time.time() - time_start > 60:
            break
        
        
def connectDoorbell(msg):
    # pair doorbell with user account  
    with open(join(path,'data.json')) as jsonFile:
        data = json.load(jsonFile)
    SmartBellID = str(data['id']) # unique ID of doorbell
    accountID = msg.payload.decode() # user account ID that doorbell is to pair with
    with open(join(path,'data.json'), 'r') as jsonFile:
        data = json.load(jsonFile)
    data['accountID'] = accountID
    with open(join(path,'data.json'), 'w') as jsonFile:
        json.dump(data, jsonFile)
    data_accountID = {"accountID": accountID, 'id': SmartBellID}
    paired = requests.post(serverBaseURL + "/update_SmartBellIDs", data_accountID).text # REST API path to store new pairing connection in SQL table 'SmartBellIDs'
    client.publish(f'pair/{accountID}', paired) # publish MQTT message to topic 'pair/accountID' to notify mobile app that pairing has been successful

    
def checkID(currentID):
    # check whether doorbell ID has been updated
    while True:
        with open(join(path,'data.json')) as jsonFile:
                data = json.load(jsonFile)
        latestID = str(data['id']) # latest value of doorbell ID
        if latestID != currentID: # if doorbell ID has been changed
            SmartBellID = currentID = latestID
            # reconfigure topics that the Raspberry Pi is subscribed to as the doorbell's ID has been updated:
            client.unsubscribe(f"id/{currentID}")
            client.subscribe(f"id/{SmartBellID}")
            client.message_callback_add(f"id/{SmartBellID}", on_message)
        time.sleep(5)
        

def on_connect(client, userdata, flags, rc):
    # callback function called when program connect to MQTT broker
    if rc == 0: # if connection is successful
        with open(join(path,'data.json')) as jsonFile:
            data = json.load(jsonFile)
        SmartBellID = str(data['id'])
        client.publish(f"connected/{SmartBellID}")
        client.subscribe(f"id/{SmartBellID}")
        client.message_callback_add(f"id/{SmartBellID}", on_message)
        checkThread = threading.Thread(target=checkID, args = (SmartBellID,)) # create thread which checks whether doorbell ID has been updated
        checkThread.start()

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