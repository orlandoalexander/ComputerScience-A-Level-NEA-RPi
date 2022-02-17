import cv2 as cv
import requests
import threading
import time
from os.path import join
import json
import numpy as np
from picamera import PiCamera
import pickle
from threading import Thread


path = "/home/pi/Desktop/NEA/ComputerScience-NEA-RPi"

serverBaseURL = "http://nea-env.eba-6tgviyyc.eu-west-2.elasticbeanstalk.com/"  # base URL to access AWS elastic beanstalk environment


def checkFaces():
    while True:
        with open(join(path,'data.json'), 'r') as jsonFile: # ensures up-to-date value for accountID is used
            time.sleep(0.5) # resolves issue with reading file immediately after it is written to (json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0))
            data = json.load(jsonFile)
            accountID = str(data['accountID'])
        dbData_accountID = {'accountID': accountID}
        faceIDs_update = (requests.post(serverBaseURL + "/checkFaces", dbData_accountID).json())
        if len(faceIDs_update) != 0:
            faceIDs_update = faceIDs_update[0] # Required 2D array stored inside 3D array (as first element)
            updateLabels_thread = Thread(target = updateLabels, args = (faceIDs_update, data, accountID))
            updateLabels_thread.start() # thread so can update another label simultanosuly 
        time.sleep(5)
        
def updateLabels(faceIDs_update, data, accountID): 
    print('Face ID change required')
    while True: # avoids running update to labelsNp while main program is running by checking if the camera is in use
        try:
            camera = PiCamera()
            break
        except:
            print('Waiting...')
            time.sleep(5)
    print('Face ID change taking place...')
    camera.close()
    print(faceIDs_update)
    time.sleep(30)# time to complete image trainign and save face ids file
    faceIDs = []
    with open(join(path,'data.json')) as jsonFile:
        data = json.load(jsonFile)
        for faceID in data[accountID]["faceIDs"]:
            faceIDs.append(faceID)
    trainingData = pickle.loads(open(join(path,"trainingData"), "rb").read())
    newFaceID_update = faceIDs_update.pop(0)[0] # access and remove first face ID (the one which the two clashing face IDs will be assigned to)
    newLabel = faceIDs.index(newFaceID_update) # value of label of new face ID     
    oldFaceID_update = faceIDs_update.pop(0)[0] # old face ID which is to be assigned to new face ID
    oldLabel = faceIDs.index(oldFaceID_update)
    faceIDs[oldLabel] = newFaceID_update # replace old faceID
    print(trainingData['labels'])
    for (index, label) in enumerate(trainingData['labels']):
        if label == oldLabel:
            trainingData['labels'][index] = newLabel # change label value of old label to new label (to keep coordination with image encoding arrays)
    print(trainingData['labels'])
    data[accountID]["faceIDs"] = faceIDs
    with open(join(path,'data.json'),'w') as jsonFile:
        json.dump(data, jsonFile)
        
    with open(join(path,'trainingData'),'wb') as file:
        file.write(pickle.dumps(trainingData)) #to open file in write mode
    print("FaceID change completed")
        
    
checkFaces_thread = threading.Thread(target = checkFaces, args =())
checkFaces_thread.start()