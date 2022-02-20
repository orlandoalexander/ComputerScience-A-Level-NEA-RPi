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
        faceIDs_update = (requests.post(serverBaseURL + "/checkFaces", dbData_accountID).json()) # request to REST API path to check whether there are any face IDs with the same name for the same user account
        if len(faceIDs_update) != 0: # if face name duplicates exist
            faceIDs_update = faceIDs_update[0] # Required 2D array stored inside 3D array (as first element)
            updateLabels_thread = Thread(target = updateLabels, args = (faceIDs_update, accountID))
            updateLabels_thread.start() # thread so can update another label simultaneously
        time.sleep(5)
        
def updateLabels(faceIDs_update, accountID):
    print('Face ID change required')
    while True: # avoids running update to labels stored in 'trainingData' while main program is running by checking if the camera is in use
        try:
            camera = PiCamera()
            break
        except: # if unable to instantiate instance of 'PiCamera', indicates that camera is currently in use by 'main_pi.py'
            print('Waiting...')
            time.sleep(5)
    print('Face ID change taking place...')
    camera.close()
    print(faceIDs_update)
    time.sleep(30) # delay to allow time to complete image training and save 'trainingData'
    faceIDs = []
    with open(join(path,'data.json')) as jsonFile:
        data = json.load(jsonFile)
        for faceID in data[accountID]["faceIDs"]:
            faceIDs.append(faceID) # store all the faceIDs associated with user's account
    trainingData = pickle.loads(open(join(path,"trainingData"), "rb").read()) # load known face encodings
    newFaceID_update = faceIDs_update.pop(0)[0] # access and remove first face ID of the two face IDs assigned to the same name - both face IDs will be assigned to this new face ID
    newLabel = faceIDs.index(newFaceID_update) # value of label of new face ID     
    oldFaceID_update = faceIDs_update.pop(0)[0] # old face ID which is to be assigned to new face ID
    oldLabel = faceIDs.index(oldFaceID_update) # label of old face ID
    faceIDs[oldLabel] = newFaceID_update # replace old face ID with new face ID
    print(trainingData['labels'])
    for (index, label) in enumerate(trainingData['labels']): # iterate through labels stored in 'trainingData' and replace the old labels with the new label, so the new label/face ID will be tagged to the face encodings associated with the old label and new label
        if label == oldLabel:
            trainingData['labels'][index] = newLabel # change label value of old label to new label
    print(trainingData['labels'])
    data[accountID]["faceIDs"] = faceIDs # save updated face IDs
    with open(join(path,'data.json'),'w') as jsonFile:
        json.dump(data, jsonFile)
    with open(join(path,'trainingData'),'wb') as file:
        file.write(pickle.dumps(trainingData)) # store updated face encodings and associated labels
    print("FaceID change completed")
        
    
checkFaces_thread = threading.Thread(target = checkFaces, args =())
checkFaces_thread.start()