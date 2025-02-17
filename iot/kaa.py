import json
import logging
import random
import signal
import string
import sys
import time
import RPi.GPIO as GPIO
import Adafruit_DHT
import requests
import numpy as np
from datetime import datetime
from threading import Thread  
import socket

import paho.mqtt.client as mqtt

DEFAULT_KPC_HOST = "mqtt.cloud.kaaiot.com"    # Platform host goes here
DEFAULT_KPC_PORT = 1883   # Platform port goes here

DCX_INSTANCE_NAME = "dcx"

APPLICATION_NAME = "IoT Dam"
APPLICATION_VERSION = "bsjs9uiikfmmfgrjlss0-v1"

token = "xup4M8aEIN" # Your token goes here

def load_json(path):
  with open(path) as json_file:
    return json.load(json_file)


def killhandle(signum, frame):
  logger.info("SIGTERM detected, shutting down")
  disconnect_from_server(client=client, host=host, port=port)
  sys.exit(0)


signal.signal(signal.SIGINT, killhandle)
signal.signal(signal.SIGTERM, killhandle)

# Configure logging
logger = logging.getLogger('mqtt-client')
logger.setLevel(logging.DEBUG)

hdl = logging.StreamHandler()
hdl.setLevel(logging.DEBUG)
hdl.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))

logger.addHandler(hdl)

# Parse command line arguments
client_id = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(6))
host = DEFAULT_KPC_HOST
port = DEFAULT_KPC_PORT
logger.info("Using endpoint token {0}, server at {1}:{2}".format(token, host, port))


def connect_to_server(client, host, port):
  logger.info("Connecting to KPC instance at {0}:{1}...".format(host, port))
  client.connect(host, port, 60)
  logger.info("Successfully connected")


def disconnect_from_server(client, host, port):
  logger.info("Disconnecting from server at {0}:{1}.".format(host, port))
  time.sleep(4)  # wait
  client.loop_stop()  # stop the loop
  client.disconnect()
  logger.info("Successfully disconnected")


# TELEMETRY section --------------------------------------
# Compose KP1 topic for data collection
data_request_id = random.randint(1, 99)
topic_data_collection = "kp1/{application_version}/{service_instance}/{resource_path}".format(
  application_version=APPLICATION_VERSION,
  service_instance=DCX_INSTANCE_NAME,
  resource_path="{token}/json/{data_request_id}".format(token=token, data_request_id=data_request_id)
)
logger.debug("Composed data collection topic: {}".format(topic_data_collection))


def compose_data_sample(level, humidity, temperature, DOOR, forecast_string):
  payload = [
    {
      "timestamp": int(round(time.time() * 1000)),
      "water_values": level,
      "humidity": humidity,
      "temperature": temperature,
      "DOOR": DOOR,
      "forecast_string": forecast_string,
    }
  ]
  return json.dumps(payload)


def on_message(client, userdata, message):
  logger.info("Message received: topic [{}]\nbody [{}]".format(message.topic, str(message.payload.decode("utf-8"))))


# Initiate server connection
client = mqtt.Client(client_id=client_id)
client.on_message = on_message
connect_to_server(client=client, host=host, port=port)
# Start the loop
client.loop_start()


GPIO.setmode(GPIO.BOARD)
GPIO.setwarnings(False)
GPIO.setup(13, GPIO.OUT)
GPIO.setup(15, GPIO.OUT)
p = GPIO.PWM(13, 50)
r = GPIO.PWM(15, 50)

GPIO.setup(22,GPIO.OUT)
GPIO.setup(32,GPIO.OUT)

GPIO.setup(38,GPIO.OUT)
GPIO.setup(40,GPIO.OUT)

flag=0

door_open = 0

URL = "http://9f844416e94f.ngrok.io/iot/store"  #"http://ec2-15-206-145-17.ap-south-1.compute.amazonaws.com/iot/store" 

class Forecast:
    '''
    Class to handle forecast functions
    '''
    
    def __init__(self, queue_size, warning_level=18, danger_level=21, highest_flood_level=23):
        self.metadata = (warning_level, danger_level, highest_flood_level)
        self.queue_size = queue_size
        self.queue = []

    def push(self, value):
        '''
        Adding values to the queue
        '''

        if len(self.queue) >= self.queue_size:
            self.queue.pop(0)
        self.queue.append(value)
    
    def make_forecast(self):
        '''
        Makes forecast based on the water values in the queue
        '''

        change_value = self.__calculate_weighted_change()
        if change_value > 0:
            forecast = np.arange(self.queue[-1], self.queue[-1] + change_value, change_value / len(self.queue))
        else:
            forecast = np.array([self.queue for _ in range(len(self.queue))])

        return self.__get_levels(forecast)

    def __get_levels(self, forecast):
        '''
        Returns water levels
        '''

        warning_level, danger_level, highest_flood_level = self.metadata

        percent_normal = (forecast < warning_level).sum() / len(forecast)
        percent_warning = ((warning_level <= forecast) & (forecast < danger_level)).sum() / len(forecast)
        percent_danger = ((danger_level <= forecast) & (forecast < highest_flood_level)).sum() / len(forecast)
        percent_hfl = (forecast >= highest_flood_level).sum() / len(forecast)

        return percent_normal, percent_warning, percent_danger, percent_hfl


    def __calculate_weighted_change(self):
        '''
        Calculates change in water level
        '''

        change_sum = 0
        for i in range(len(self.queue), 1, -1):
            change_sum += (1 / i) * (self.queue[-(i - 1)] - self.queue[-i])
        return change_sum


def upload_to_database(created_at,level, humidity, temperature, DOOR,forecast_string):
    '''
    Uploads to database
    '''
    
    print(level, humidity, temperature, DOOR,forecast_string)
    payload = {'created_at':created_at,'water_level': level,'humidity': humidity,'temperature': temperature, 'door_open': DOOR, 'forecast_string':forecast_string}
    print(created_at)

    headers= {}

    response = requests.request("POST", URL, headers=headers, data=payload)

    payload = compose_data_sample(level,humidity, temperature, DOOR, forecast_string)
    result = client.publish(topic=topic_data_collection, payload=payload)

    print(response.text.encode('utf8'))


forecast=Forecast(216)

start_time = time.time() # This will be used to upload values to DB after every 3 seconds

while True: 
        
       GPIO.output(38,1)  
       TRIG = 16
       ECHO = 18
     
       GPIO.setup(TRIG,GPIO.OUT)
       GPIO.setup(ECHO,GPIO.IN)
       GPIO.output(TRIG, True)
       time.sleep(0.00001)
       GPIO.output(TRIG, False)

    
       while GPIO.input(ECHO)==0:
          pulse_start = time.time()
    

    
       while GPIO.input(ECHO)==1:
          pulse_end = time.time()

       pulse_duration = pulse_end - pulse_start

       distance = pulse_duration * 17150

       level = round(distance+1.15, 2)
    
       level = round(27 - level)


       print("level:", level, "cm")
   
    
       sensor = Adafruit_DHT.DHT11
       DHT11_pin = 17
       humidity, temperature = Adafruit_DHT.read_retry(sensor, DHT11_pin)
       if humidity is not None and temperature is not None:
          print('Temperature={0:0.1f}*C  Humidity={1:0.1f}%'.format(temperature, humidity))
       else:
          print('Failed to get reading from the sensor. Try again!')

    # You will get 4 levels of water in percentage
    # You can use this to adjust door height
    # For example:
    # (1.0, 0.0, 0.0, 0.0) the forecast for next window says 100 percent of water will remain at normal level
    # (0.21052631578947367, 0.7894736842105263, 0.0, 0.0) says there is ~ 0.21 percent chance that water will rise above warning and 78 percent chance water will rise above danger
    # Using this you can open doors before high levels of water is reached
    # Uncomment the code below
       forecast.push(level)
       normal_level, warning_level, danger_level, highest_flood_level = forecast.make_forecast()
    
       water_values = forecast.make_forecast()
       water_list = list(water_values)
       index = np.argmax(water_list)
       forecast_string = 'Normal' if index == 0 else 'Warning' if index == 1 else 'Danger' if index == 2 else 'HFL' if index == 3 else 'No Data'
 
       print('Forecast completed')

    
       door_open = 0    
       print(flag,'flag')
       if(flag == 0): 
         p.start(7.5)
         r.start(7.5)
         if(level > 17):
            door_open= 1
            p.ChangeDutyCycle(12.5)
         if(level > 20.5):   
            door_open= 2
            r.ChangeDutyCycle(12.5)
            time.sleep(0.01) 
            GPIO.output(22,1)
            GPIO.output(32,GPIO.HIGH)
            GPIO.output(40,1)
         else:
            GPIO.output(22,0)
            GPIO.output(32,GPIO.LOW)
            GPIO.output(40,0)

       created_at = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    
    

       if time.time() - start_time >= 3:
          upload_thread = Thread(target=upload_to_database, args=(created_at,level, humidity, temperature, door_open,forecast_string))
          upload_thread.start()
          start_time = time.time()

       print('Finished uploading')
       time.sleep(0.2)