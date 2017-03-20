import RPi.GPIO as GPIO
import subprocess
import time

class relay(object):
	"""Class that controls an AC/DC control relay

	Attributes:
	name: Relay name (IE - Heater, Light, etc.
	GPIO_PIN: BCM GPIO PIN on rasperry pi that the AC/D control relay is plugged into
	"""

	def __init__(self,name="relay",GPIO_PIN=18,type="always_off"):
		"""Return a relay object whose name is  *name*.""" 
		self.name = name
		self.GPIO_PIN = GPIO_PIN
		self.type = type
		#setup GPIO Pins
		GPIO.setwarnings(False) 
		GPIO.setmode(GPIO.BCM)
		GPIO.setup(GPIO_PIN, GPIO.OUT)
		

	def switchHigh(self):
		try:
			GPIO.output(self.GPIO_PIN,GPIO.HIGH)
			time.sleep(3)
		except:
			return False
		return True

	def switchLow(self):
		try:
			GPIO.output(self.GPIO_PIN,GPIO.LOW)
			time.sleep(3)
		except:
			return False
		
		return True

	def status(self):
		#return current status of switch, 0 or 1
		try:
			p = subprocess.Popen(["gpio -g read " + str(self.GPIO_PIN)],shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
			message =  p.communicate(input)
			return message[0].rstrip()
		except:
			return False

'''
heater = relay()
print heater.status()
heater.switch_high()
heater.switch_low()
'''