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
    # check whether SQL table 'vsitorLog' contains any duplicate face names associated with the same user account
    while True:
        with open(join(path,'data.json'), 'r') as jsonFile: # ensures up-to-date value for accountID is used
            time.sleep(0.5) # avoids concurrent access errors for 'data.json' file
            data = json.load(jsonFile)  # load json file as json object
            accountID = str(data['accountID'])  # retrieve user's account ID stored under key 'accountID' in json object 'data'
        dbData_accountID = {'accountID': accountID}
        faceIDs_update = (requests.post(serverBaseURL + "/checkFaces", dbData_accountID).json()) # request to REST API path to check whether there are any face IDs with the same name for the same user account
        if len(faceIDs_update) != 0: # if face name duplicates exist
            faceIDs_update = faceIDs_update[0] # access required 2D array which is first element stored inside 3D array
            updateLabels_thread = Thread(target = updateLabels, args = (faceIDs_update, accountID)) # function called in thread so can update another label simultaneously
            updateLabels_thread.start()
        time.sleep(5)
        
def updateLabels(faceIDs_update, accountID):
    # update labels for face encodings in trained data set where there are duplicate face names for identified faces associated with the same user account
    while True: # avoids running update to labels stored in 'trainingData' while main program is running by checking if the camera is in use
        try:
            camera = PiCamera()
            break
        except: # if unable to instantiate instance of 'PiCamera', indicates that camera is currently in use by 'main_pi.py'
            time.sleep(5)
    camera.close() # close camera instance
    time.sleep(30) # delay to allow time to complete image training and save 'trainingData'
    faceIDs = []
    with open(join(path,'data.json')) as jsonFile:
        data = json.load(jsonFile)
        for faceID in data[accountID]["faceIDs"]:
            faceIDs.append(faceID) # store all the faceIDs associated with user's account
    trainingData = pickle.loads(open(join(path,"trainingData"), "rb").read()) # load known face encodings
    newFaceID_update = faceIDs_update.pop(0)[0] # access and remove first face ID of the face IDs assigned to the duplicate name - all face IDs associated with the duplicate name will be assigned to this new face ID
    newLabel = faceIDs.index(newFaceID_update) # label of new face ID
    oldFaceID_update = faceIDs_update.pop(0)[0] # old face ID which is to be assigned to 'newFaceID_update'
    oldLabel = faceIDs.index(oldFaceID_update) # label of old face ID
    faceIDs[oldLabel] = newFaceID_update # replace old face ID with new face ID
    for (index, label) in enumerate(trainingData['labels']): # iterate through labels stored in 'trainingData' and replace the old labels with the new label, so the face encodings of the duplicate face names will be tagged with the new label
        if label == oldLabel: # if label needs to be updated
            trainingData['labels'][index] = newLabel # change label value of old label to new label
    data[accountID]["faceIDs"] = faceIDs # save updated face IDs
    with open(join(path,'data.json'),'w') as jsonFile:
        json.dump(data, jsonFile)
    with open(join(path,'trainingData'),'wb') as file:
        file.write(pickle.dumps(trainingData)) # store updated face encodings and associated labels

checkFaces_thread = threading.Thread(target = checkFaces, args =())
checkFaces_thread.start()