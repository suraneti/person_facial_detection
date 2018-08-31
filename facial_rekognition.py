from darkflow.net.build import TFNet
from aws_rekognition import Rekognition

import cv2
import threading
import numpy as np
import requests

# Enable debug to print all response data
DEBUG = False

# Enable darkflow will also enable tensorflow
# for person detection
ENABLE_DARKFLOW = False

# If enable caffe method, opencv face detection method
# will disable
ENABLE_CAFFE_NET = True

# Tensorflow & Darkflow
if ENABLE_DARKFLOW:
    options = {"model": "cfg/yolo.cfg", "load": "bin/yolo.weights", "threshold": 0.1}
    tfnet = TFNet(options)

# Camera
camera = cv2.VideoCapture(1)
camera.set(3, 800)
camera.set(4, 800)

# Load facial detection network
if ENABLE_CAFFE_NET:
    # Caffe net
    caffe_net = cv2.dnn.readNetFromCaffe('deploy.prototxt.txt', 'res10_300x300_ssd_iter_140000.caffemodel')
else:
    # Face cascad classify
    face_cascade = cv2.CascadeClassifier("bin/haarcascade_frontalface_default.xml")

current_frame = None
darkflow_resp = None

def aws_rekognition():
    rekognition = Rekognition(img='pre_predict.jpg')
    rekognition.upload_image()
    response = rekognition.face_recognition()

    frame = cv2.imread('pre_predict.jpg')
    height, width, _ = frame.shape

    x = int(response["SearchedFaceBoundingBox"]["Left"] * width)
    y = int(response["SearchedFaceBoundingBox"]["Top"] * height)
    w = int(response["SearchedFaceBoundingBox"]["Width"] * width)
    h = int(response["SearchedFaceBoundingBox"]["Height"] * height)

    # Draw rectangle
    cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 2)

    # Draw background
    cv2.rectangle(frame,
        (x - 1, y - 2),
        (x + 170, y - 35),
        (255, 0, 0),
        -1)

    # Draw text
    cv2.putText(img=frame,
        text=response["FaceMatches"][0]["Face"]["ExternalImageId"],
        org=(x + 10, y - 10),
        fontFace=cv2.FONT_HERSHEY_SIMPLEX,
        fontScale=0.8,
        color=(0, 0, 0),
        thickness=2)

    cv2.imwrite('post_predict.jpg', frame)

    print('Detected : ' + response["FaceMatches"][0]["Face"]["ExternalImageId"])

def darkflow():
    result = tfnet.return_predict(current_frame)
    final_result = sorted(result, key=lambda k:(k['label']=='person', k['confidence']), reverse=True)
    if DEBUG:
        print(final_result)
    global darkflow_resp
    darkflow_resp = final_result

def initial_camera():
    _, frame = camera.read()

    if ENABLE_DARKFLOW:
        global current_frame
        current_frame = frame
        thread = threading.Thread(target=darkflow)
        thread.start()

    while(True):
        _, frame = camera.read()
        raw_frame = frame.copy()

        if ENABLE_DARKFLOW:
            if thread.is_alive():
                pass
            else:
                current_frame = frame
                thread = threading.Thread(target=darkflow)
                thread.start()
       
        ##########################################
        #    CAFFE_NET_FACE_DETECTION METHOD     #
        ##########################################
        if ENABLE_CAFFE_NET:
            h, w = frame.shape[:2]

            blob = cv2.dnn.blobFromImage(cv2.resize(frame, (300, 300)), 1.0,
                    (300, 300), (104.0, 177.0, 123.0))

            caffe_net.setInput(blob)
            detections = caffe_net.forward()

            # loop over the detections
            faces_number = 1
            for i in range(0, detections.shape[2]):
                # extract the confidence (i.e., probability) associated with the
                # prediction
                confidence = detections[0, 0, i, 2]

                # filter out weak detections by ensuring the `confidence` is
                # greater than the minimum confidence
                if confidence < 0.5:
                    continue

                # compute the (x, y)-coordinates of the bounding box for the
                # object
                box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                startX, startY, endX, endY = box.astype("int")

                # draw the bounding box of the face along with the associated
                # probability
                text = "Face" + str(faces_number) + " {:.2f}%".format(confidence * 100)
                y = startY - 10 if startY - 10 > 10 else startY + 10
                
                # Draw rectangle
                cv2.rectangle(frame, (startX, startY), (endX, endY),
                    (255, 0, 0), 2)

                # Draw background
                cv2.rectangle(frame,
                    (startX - 1, startY - 2),
                    (startX + 200, startY - 35),
                    (255, 0, 0),
                    -1)

                # Draw text
                cv2.putText(frame, text, (startX, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)

                # Increasing faces number of detection
                faces_number += 1

                # AWS faces index
                if (confidence * 100) >= 98:
                    resp = requests.get('http://172.168.99.240:3268/capture/')
                    if resp.text == '1':
                        resp = requests.post('http://172.168.99.240:3268/capture/0')
                        cv2.imwrite('pre_predict.jpg', raw_frame)
                        print('Start AWS Threading')
                        aws_thread = threading.Thread(target=aws_rekognition)
                        aws_thread.start()

        ##########################################
        #      OPENCV_FACE_DETECTION METHOD      #
        ##########################################
        else:
            # Our operations on the frame come here
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, 1.3, 5)

            face_num = 1
            # Display the resulting frame
            for (x,y,w,h) in faces:
                cv2.rectangle(frame,(x,y),(x+w,y+h),(255,0,0),2)
                #  roi_gray = gray[y:y+h, x:x+w]
                #  roi_color = frame[y:y+h, x:x+w]
                #  face_capture = frame[y:y+h, x:x+w]

                # Draw text background
                cv2.rectangle(frame,
                    (x - 1, y - 2),
                    (x + 100, y - 35),
                    (255, 0, 0),
                    -1)

                # Draw face label
                cv2.putText(img=frame,
                    text="face " + str(face_num),
                    org=(x + 10, y - 10),
                    fontFace=cv2.FONT_HERSHEY_SIMPLEX,
                    fontScale=0.8,
                    color=(0, 0, 0),
                    thickness=2,
                    lineType=cv2.LINE_AA)
                face_num += 1 

        if ENABLE_DARKFLOW:
            if darkflow_resp:
                for i in darkflow_resp:
                    if i['confidence'] > 0.5: 
                        # Draw rectangle
                        cv2.rectangle(frame,
                            (i["topleft"]["x"], i["topleft"]["y"]),
                            (i["bottomright"]["x"], i["bottomright"]["y"]),
                            (0, 255, 0),
                            2)

                        # Draw text background
                        cv2.rectangle(frame,
                            (i["topleft"]["x"] - 1, i["topleft"]["y"] - 2),
                            (i["topleft"]["x"] + 180, i["topleft"]["y"] - 38),
                            (0, 255, 0),
                            -1)
                        
                        # Draw text label
                        text_x, text_y = i["topleft"]["x"] + 10, i["topleft"]["y"] - 10    
                        cv2.putText(img=frame,
                            text=i["label"] + ' ' + str(round(i["confidence"], 2)),
                            org=(text_x, text_y),
                            fontFace=cv2.FONT_HERSHEY_SIMPLEX,
                            fontScale=0.8,
                            color=(0, 0, 0),
                            thickness=2)

        cv2.imshow('frame', frame)
        # cv2.imshow('face', face_capture)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    camera.release()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    initial_camera()