#!/usr/bin/python3
import cv2 as cv
from picamera.array import PiRGBArray
from picamera import PiCamera
import time
import json
import boto3
from os.path import join
import os
import threading
import paho.mqtt.client as mqtt
import requests
from cryptography.fernet import Fernet
import face_recognition
import pickle

path = "/home/pi/Desktop/NEA/ComputerScience-NEA-RPi"

serverBaseURL = "http://nea-env.eba-6tgviyyc.eu-west-2.elasticbeanstalk.com/"  # base URL to access AWS elastic beanstalk environment

haarCascade = cv.CascadeClassifier(join(path,"haar_face_alt2.xml")) # reads in the xml haar cascade file

windowSize_mobile = (640, 1136) # mobile phone screen size

class buttonPressed():
    def __init__(self):
        with open(join(path,'data.json'), 'r') as jsonFile: # ensures up-to-date value for accountID is used
            time.sleep(0.5) # resolves issue with reading file immediately after it is written to (json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0))
            data = json.load(jsonFile)
            self.accountID = str(data['accountID'])
        self.visitID = self.create_visitID()
        self.publish_message_ring()
        with open(join(path,'data.json')) as jsonFile:
            self.data = json.load(jsonFile)
        if self.accountID not in self.data: # if data for account not yet stored
            self.data.update({self.accountID:{"faceIDs":[]}}) # updates json file to create empty parameter to store names of known visitors associated with a specific accountID
            with open(join(path,'data.json'),'w') as jsonFile:
                json.dump(self.data, jsonFile)

    def captureImage(self):
        self.camera = PiCamera()
        self.rawCapture = PiRGBArray(self.camera) # using PiRGBArray increases efficiency when accessing camera stream 
        self.trainingImages = []
        self.trainingImages_faceRGB = []
        self.faceDetected = False
        time.sleep(0.155) # delay to allow camera to warm up
        attempts = 0
        while attempts < 2: # time consuming to capture images and analyse for presence of face, so only attempt process of capturing images twice
            faceRGBImages = []
            self.rawCapture.truncate(0) # clear any data from the camera stream
            self.camera.capture(self.rawCapture, format="bgr") # captures camera stream in 'bgr' format (opencv array requires this)
            self.faceBGR = cv.flip(self.rawCapture.array,0) # bgr is format required for opencv, so capture image in this format
            self.faceGray = cv.cvtColor(self.faceBGR, cv.COLOR_BGR2GRAY) # change to gray for opencv
            self.faceRGB = cv.cvtColor(self.faceBGR, cv.COLOR_BGR2RGB) # change to rgb for face_recognition module
            #cv.imshow('gray', self.faceGray)
            #cv.waitKey(0)
            #cv.imshow('bgr', self.faceRGB)
            #cv.waitKey(0)
            if attempts == 0:
                self.uploadImage = threading.Thread(target=self.formatImage, args=(self.faceBGR,), daemon=False)
                self.uploadImage.start()  # starts the thread which will run in pseudo-parallel to the rest of the program
            faceRGBImages.append(self.faceRGB)
            # check if face exists as much quicker than doing facial recognition - so can check whether need to capture another image 
            faceDetected = haarCascade.detectMultiScale(self.faceGray, scaleFactor=1.01, minNeighbors=6)  # returns rectangular coordinates of a face.
            # scaleFactor is the percentage by which the image is resized on each iteration of the algorithm to attempt to detect a face in the image, as the face size used in the haar cascade xml is constant, but face sizes in the test image may vary. A small percentage value (i.e. 1.05 which would reduce image size by 5% on each iteration) would mean there is a small step for each resizing, so there is a greater chance of correctly detecting all the faces in the image, although it will be slower than using a larger scale factor
            # minNeighbours specifies how many neighbours each candidate rectangle should have to retain it. In other words, the minimum number of positive rectangles (detect facial features) that need to be adjacent to a positive rectangle in order for it to be considered actually positive. A higher value of minNeighbours will result in less detections but with high quality - somewhere between 3-4
            blurFactor = cv.Laplacian(self.faceGray, cv.CV_64F).var()# Laplacian operator calculates the gradient change values in an image (i.e. transitions from black to white in greyscale image), so it is used for edge detection. Here, the variance of this operator on each image is returned; if an image contains high variance then there is a wide spread of responses, both edge-like and non-edge like, which is representative of a normal, in-focus image. But if there is very low variance, then there is a tiny spread of responses, indicating there are very little edges in the image, which is typical of a blurry image
            num_faceDetected = len(faceDetected) # finds number of faces detected in image
            print(blurFactor, num_faceDetected)
            if num_faceDetected >= 1 and blurFactor >= 25: # if at least 1 face has been detected and image isn't blurry, save the image
                self.trainingImages.extend(faceRGBImages) # ensures at least two images of visitor are stored for training
                self.faceDetected = True
                break # two satisfactury images are captured so do not attempt capturing images again
            else:
                attempts +=1
        if self.faceDetected == True:
            print('Face detected')
            self.facialRecognition() # run facial recognition algorithm

        else:
            print('No face detected')
            self.faceID = "NO_FACE"
            self.update_visitorLog()
            self.camera.close()
            print("Quit")
            quit()
            
            
    def recognise(self, faceRGB):
        # load the known faces and embeddings saved in last file
        fileName = join(path,"trainingData")
        if not os.path.isfile(fileName):
            return 'Unknown', False
        
        data = pickle.loads(open(fileName, "rb").read())
 
        encodings = face_recognition.face_encodings(faceRGB)
        

        # loop over the facial embeddings incase
        # we have multiple embeddings for multiple fcaes
        for encoding in encodings:
        #Compare encodings with encodings in data["encodings"]
        #Matches contain array with boolean values True and False
            matches = face_recognition.compare_faces(data["encodings"], encoding)
            #set name =unknown if no encoding matches
            # check to see if we have found a match
            if True in matches:
            #Find precogniseositions at which we get True and store them
                matchedIndexes = [index for (index, match) in enumerate(matches) if match]
                labelCount = {}
                # loop over the matched indexes and maintain a count for
                # each recognized face face
                for index in matchedIndexes:
                    #Check the names at respective indexes we stored in matchedIdxs
                    label = data["labels"][index]
                    #increase count for the name we got
                    labelCount[label] = labelCount.get(label, 0) + 1 # starts at 0 and adds 1 to counter value
                    #set name which has highest count
                label = max(labelCount, key=labelCount.get) # return key with greatest value (i.e. label with greatest number of matches)
                # will update the list of names
                # do loop over the recognized faces
                matchCount = labelCount[label]
                actualCount = 0
                for i in data['labels']:
                    if i == label:
                        actualCount +=1
                print('Matched labels:', matchCount, 'Total labels:', actualCount) # check what what percentage of traine images sample image matches - avoid false positives
                if matchCount/actualCount > 0.5:
                    print('Label',label, 'Count', labelCount)
                    return label, True
                else:
                    return 'Unknown', False
            else:
                return 'Unknown', False
        return 'Unknown', False


    def facialRecognition(self):        
        self.faceIDs = []
        with open(join(path,'data.json')) as jsonFile:
            self.data = json.load(jsonFile)
            for faceID in self.data[self.accountID]["faceIDs"]:
                self.faceIDs.append(faceID)
        
        self.label, self.faceRecognised = self.recognise(self.faceRGB) # get label for captured training image

        if self.faceRecognised == True:
            self.faceID = self.faceIDs[self.label]
            print('Face ID:', self.faceID) 
        else:
            self.faceID = self.create_faceID()
            print('New face')

        self.update_visitorLog()
        
        if self.faceID not in self.faceIDs: # if new face 
            self.faceIDs.append(self.faceID)
            self.label = self.faceIDs.index(self.faceID) # create new label if face doesn't currently exist
            self.update_knownFaces()
            
        with open(join(path,'data.json'), 'w') as jsonFile:
            json.dump(self.data, jsonFile)
        print("Training") 
        self.thread_updateTraining = threading.Thread(target=self.updateTraining, args=(), daemon=False)
        self.thread_updateTraining.start()  # starts the thread which will run in pseudo-parallel to the rest of the program
           
           
           
    def train(self, faceRGB, label):
        boxes = face_recognition.face_locations(faceRGB,model='hog')
        # compute the facial embedding for the any face
        encodings = face_recognition.face_encodings(faceRGB, boxes)
        # loop over the encodings
        for encoding in encodings:
            self.encodings.append(encoding)
            self.labels.append(label)
        return self.encodings, self.labels
        
    
    def updateTraining(self):
        self.encodings = []
        self.labels = []
        attempts = 0
        while attempts < 2: # camera captures more images to aid facial recognition training algorithm
            self.rawCapture.truncate(0) # clear the stream in preparation for the next frame
            self.camera.capture(self.rawCapture, format="bgr") # captures camera stream in 'bgr' format (opencv arr$                img = cv.flip(self.rawCapture.array,0) # 'img' stores matrix array of the capture image
            img = cv.flip(self.rawCapture.array,0) # bgr is format required for opencv, so capture image in this format
            #faceRGB = img
            faceGray = cv.cvtColor(img, cv.COLOR_BGR2GRAY) # faceGray format for haar cascade
            faceRGB = cv.cvtColor(img, cv.COLOR_BGR2RGB) # faceRGB format for facial-recognition module
            faceDetected = haarCascade.detectMultiScale(faceGray, scaleFactor=1.01, minNeighbors=6)  # returns rectangular coordinates of a face.
            # scaleFactor is the percentage by which the image is resized on each iteration of the algorithm to attempt to detect a face in the image, as the face size used in the haar cascade xml is constant, but face sizes in the test image may vary. A small percentage value (i.e. 1.05 which would reduce image size by 5% on each iteration) would mean there is a small step for each resizing, so there is a greater chance of correctly detecting all the faces in the image, although it will be slower than using a larger scale factor
            # minNeighbours specifies how many neighbours each candidate rectangle should have to retain it. In other words, the minimum number of positive rectangles (detect facial features) that need to be adjacent to a positive rectangle in order for it to be considered actually positive. A higher value of minNeighbours will result in less detections but with high quality - somewhere between 3-4
            blurFactor = cv.Laplacian(faceGray, cv.CV_64F).var()# Laplacian operator calculates the gradient change values in an image (i.e. transitions from black to white in greyscale image), so it is used for edge detection. Here, the variance of this operator on each image is returned; if an image contains high variance then there is a wide spread of responses, both edge-like and non-edge like, which is representative of a normal, in-focus image. But if there is very low variance, then there is a tiny spread of responses, indicating there are very little edges in the image, which is typical of a blurry image
            num_faceDetected = len(faceDetected) # finds number of faces detected in image
            if num_faceDetected >=1 and blurFactor >= 25: # if at least 1 face has been detected and image isn't blurry, save the image as it will contribute to the facial recognition training data set
                self.trainingImages.append(faceRGB)
            attempts +=1
        
        self.camera.close()

        self.data[self.accountID]["faceIDs"] = self.faceIDs
        self.data['training'] = 'True' # new doorbell ringing thread can now be created as camera is closed
        
        with open(join(path,'data.json'), 'w') as jsonFile:
            json.dump(self.data, jsonFile)
            
        for faceRGB in self.trainingImages:
            newFace_data = []
            if self.faceRecognised == True:
                label, faceRecognised = self.recognise(faceRGB) # get label for captured training image
                if label == self.label: # if training image  has same label as label of original visitor image captured
                    self.encodings, self.labels = self.train(faceRGB, label)
                    print('Image trained')
                    cv.imwrite((join(path,"Photos/faceRecognised.png")), faceRGB) #save first image captured as most likely to be looking at doorbell camera
            elif self.faceRecognised == False:
                self.encodings, self.labels = self.train(faceRGB, self.label)
                print('Training image is new face')
                cv.imwrite((join(path,"Photos/faceNotRecognised.png")), faceRGB) #save first image captured as most likely to be looking at doorbell camera
            
        fileName = join(path,"trainingData")
        if os.path.isfile(fileName):
             # load the known faces and embeddings saved in last file
            trainingData = pickle.loads(open(join(path,"trainingData"), "rb").read())
            trainingData['encodings'].extend(self.encodings) # add latest visitor image encoding data to list as new data elements
            trainingData['labels'].extend(self.labels)
        else:
            trainingData = {'encodings': self.encodings, 'labels': self.labels}
        
        print(trainingData['labels'])
        f = open(join(path,"trainingData"), "wb")
        f.write(pickle.dumps(trainingData))#to open file in write mode
        f.close()
        #to close file
            
        self.data['training'] = 'False'
        with open(join(path,'data.json'), 'w') as jsonFile:
            json.dump(self.data, jsonFile)
            
        print("Quit")
        quit()


    def create_visitID(self):
        # creates a unique visitID for each visit
        self.data_vistID = {"field": "visitID"}
        visitID = requests.post(serverBaseURL + "/create_ID", self.data_vistID).text
        return visitID


    def create_faceID(self):
        # creates a unique faceID for the face captured
        self.data_faceID = {"field": "faceID"}
        faceID = requests.post(serverBaseURL + "/create_ID", self.data_faceID).text
        return faceID


    def update_visitorLog(self):
        self.data_visitorLog = {"visitID": self.visitID, "imageTimestamp": (str(time.strftime("%H.%M"))+','+str(time.time())), "faceID": self.faceID, "accountID": self.accountID}
        requests.post(serverBaseURL + "/update_visitorLog", self.data_visitorLog)
        return

    def update_knownFaces(self):
        self.data_knownFaces = {"faceID": self.faceID, "faceName": "", "accountID": self.accountID}
        requests.post(serverBaseURL + "/update_knownFaces", self.data_knownFaces)
        return

    def formatImage(self, visitorImage):
        visitorImage_cropped_w = round(int(windowSize_mobile[0]) * 0.93)
        visitorImage_cropped_h = round(int(windowSize_mobile[1]) * 0.54)
        scaleFactor = visitorImage_cropped_h / visitorImage.shape[0] # scaleFactor is factor by which height of image must be scale down to fit screen
        visitorImage = cv.resize(visitorImage,
                                 (int(visitorImage.shape[1] * scaleFactor), int(visitorImage.shape[0] * scaleFactor)),
                                 interpolation=cv.INTER_AREA) # scales down width and height of image to match required image height
        visitorImage_centre_x = visitorImage.shape[1]//2
        visitorImage_x = visitorImage_centre_x - visitorImage_cropped_w // 2  # floored division for pixels as must be integer
        if visitorImage_x < 0:
            visitorImage_x = 0
        visitorImage_cropped = visitorImage[0:visitorImage.shape[0],
                               visitorImage_x:visitorImage_x + visitorImage_cropped_w] # crops image width to fit screen (with centre of image the face of the visitor, if a face can be detected)
        self.path_visitorImage = join(path, 'Photos/visitorImage.png')
        cv.imwrite(self.path_visitorImage, visitorImage_cropped)
        self.uploadAWS_image(Bucket="nea-visitor-log", Key = self.visitID)

    def uploadAWS_image(self, **kwargs):
        fernet = Fernet(self.accountID.encode()) # instantiate Fernet class with users accountID as the key
        self.data_S3Key = {"accountID": self.accountID}
        hashedKeys = requests.post(serverBaseURL + "/get_S3Key", self.data_S3Key).json() # returns json object with encoded keys
        accessKey = fernet.decrypt(hashedKeys["accessKey_encrypted"].encode()).decode() # encoded byte string returned so must use 'decode()' to decode it
        secretKey = fernet.decrypt(hashedKeys["secretKey_encrypted"].encode()).decode()
        s3 = boto3.client("s3", aws_access_key_id=accessKey, aws_secret_access_key=secretKey)  # initialises a connection to the S3 client on AWS using the 'accessKey' and 'secretKey' sent to the API
        s3.upload_file(Filename=self.path_visitorImage, Bucket=kwargs["Bucket"], Key=kwargs["Key"])  # uploads the txt file to the S3 bucket called 'nea-audio-messages'. The name of the txt file when it is stored on S3 is the 'messageID' of the audio message which is being stored as a txt file.
        print("Uploaded")
  
        return
    
    def publish_message_ring(self):
        client.publish("ring/{}".format(self.accountID), "{}".format(str(self.visitID)))
        return

    def publish_message_visitor(self):
        client.publish("visit/{}".format(self.accountID), "{}".format(str(self.visitID)))
        return
    


def on_connect(client, userdata, flags, rc):
    if rc == 0: # if connection is successful
        client.publish('connected','')
    else:
        # attempts to reconnect
        client.on_connect = on_connect
        client.username_pw_set(username="yrczhohs", password = "qPSwbxPDQHEI")
        client.connect("hairdresser.cloudmqtt.com", 18973)
        
def run():
    client.username_pw_set(username="yrczhohs", password = "qPSwbxPDQHEI")
    client.on_connect = on_connect # creates callback for successful connection with broker
    client.connect("hairdresser.cloudmqtt.com", 18973) # parameters for broker web address and port number
    buttonPressed().captureImage()
    
client = mqtt.Client()



        
