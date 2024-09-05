# skateboard.py
# DIY Electric Skateboard
# Created by Matthew Timmons-Brown, The Raspberry Pi Guy
# Modifications made by Austin and Derek Dicker

import pigpio  		# controls GPIOs
import time		# manages delays, measure elapse time, and handle timing ops
import cwiid		# manages Wii remote (e.g., reads inputs)
import sys		# provides access to some variables used by the interpreter 
import threading	# allows for the creation of multiple threads within a program
import subprocess	# allows for spawning of new processes - enables Python script execution

pi = pigpio.pi()
is_debug = "debug" in sys.argv

# GPIO Mapping to Headers on the Raspberry Pi Zero W 40-pin header
motor = 18		# Note that GPIO_18 maps to pin 12 on the 40-pin header	/ PWM0 Output controls the motors
led = 17		# Note that GPIO_17 maps to pin 11 on the 40-pin header	/ GPIO Output controls the Power Button LED	
button = 27		# Note that GPIO_27 maps to pin 13 on the 40-pin header / GPIO Input controls the Power Button On/Off
lights_on = 26		# Note that GPIO_26 maps to pin 37 on the 40-pin header / Not Implemented in our Design Yet
lights_off = 16		# Note that GPIO_16 maps to pin 36 on the 40-pin header / Not Implemented in our Design Yet

wiimote_bluetooth = "B8:AE:6E:31:1B:83"  # Changed for Dicker's Wii (BLACK)
powerdown = ["sudo", "shutdown", "now"]

stop_val = False

class Skateboard(object):
	""" An all-powerful skateboard controller """

	# Constants for values used by class
	min_speed = 1720
	max_speed = 1100

	servo_smooth = 2
	smooth_sleep = 0.005
	accel_sleep = 0.015
	indicator_lights_on = 0

	# Initial setup of pins and various values
	def __init__(self):
		pi.set_PWM_frequency(motor, 50)
		pi.set_mode(led, pigpio.OUTPUT)
		pi.set_mode(button, pigpio.INPUT)
		pi.set_mode(lights_on, pigpio.OUTPUT)		# Not Implemented in our Design Yet
		pi.set_mode(lights_off, pigpio.OUTPUT)		# Not Implemented in our Design Yet
		pi.set_pull_up_down(button, pigpio.PUD_UP)
		self.__speed = 1500
		self.speed = 1500

	# Decorator to push speed value to ESC as soon as when changed
	@property
	def speed(self):
		return self.__speed
	
	# This code is designed to adjust the motor speed in a smooth, gradual manner. 
	# It prevents sudden changes in speed by incrementally adjusting the current speed 
	# toward the target value. This gradual change can be important in applications 
	# where sudden changes could be dangerous or undesirable, such as in motor control 
	# for an electric skateboard. The use of sleep intervals ensures that the adjustments
	# happen over time, leading to a smooth acceleration or deceleration.
	@speed.setter
	def speed(self, value):
		value = max(min(value, Skateboard.min_speed), Skateboard.max_speed)
		while abs(value-self.__speed) > Skateboard.servo_smooth:
			direction = cmp(value, self.__speed)
			self.__speed += direction * Skateboard.servo_smooth
			pi.set_servo_pulsewidth(motor, self.__speed)
			time.sleep(Skateboard.smooth_sleep)
		pi.set_servo_pulsewidth(motor, value)		
		self.__speed = value
		time.sleep(Skateboard.accel_sleep)
	
	# Blinks the ring LED of the power button on electric skateboard
	def blinky(self,times,period):
		for i in range (1,times):
			pi.write(led,1)
			time.sleep(period)
			# pi.write(led,0)	DDD Note:  Commented out to root cause LED turning on
			# time.sleep(period)   DDD Note:  Commented out to root cause LED turning on

	# We are not yet including the Arduino code for LEDs
	# Toggles an Arduino that toggles the neopixels on the bottom of the electric skateboard
	def arduino_trigger(self):
		if Skateboard.indicator_lights_on == 0:
			pi.write(lights_on,1)
			Skateboard.indicator_lights_on = 1
			self.wii.led = 15
		elif Skateboard.indicator_lights_on == 1:
			pi.write(lights_off,1)
			pi.write(lights_on,0)
			Skateboard.indicator_lights_on = 0
			self.wii.led = 0
		time.sleep(0.5) # Let's hope I don't activate this whilst on the board and die from this half second delay

	# Connects to Wiimote with specified mac address
	def connection_process(self):
		connected = False
		while not connected:
			self.blinky(5,0.4)
			try:
				self.wii = cwiid.Wiimote(bdaddr = wiimote_bluetooth)
				connected = True
				self.blinky(40,0.03)
				self.wii.rpt_mode = cwiid.RPT_BTN
				self.wii.rumble = 1
				time.sleep(1)
				self.wii.rumble = 0
			except RuntimeError:
				pass

	# Controller-skateboard interface
	def run_process(self):
		global stop_val
		pi.write(led, 1)
		while (stop_val == False):
			self.get_status()
			if self.status_button:
				self.wii.rumble=1
				time.sleep(2)
				self.wii.rumble=0
				raise RuntimeError("Status Button")
		
			if (self.buttons & cwiid.BTN_A):
				self.arduino_trigger()
				
			if (self.buttons & cwiid.BTN_B):
				self.speed = 1500
				time.sleep(0.5)
			if (self.buttons & cwiid.BTN_DOWN):
				self.speed += 1
			if (self.buttons & cwiid.BTN_UP):
				self.speed -= 1
			if (self.buttons & cwiid.BTN_PLUS):
				Skateboard.accel_sleep += 0.005
				time.sleep(0.5)
				if Skateboard.accel_sleep >= 0.1:
					Skateboard.accel_sleep = 0.1
				print(Skateboard.accel_sleep)
			if (self.buttons & cwiid.BTN_MINUS):
				Skateboard.accel_sleep -= 0.005
				time.sleep(0.5)
				if Skateboard.accel_sleep <= 0:
					Skateboard.accel_sleep = 0
				print(Skateboard.accel_sleep)
		self.speed = 1500 #If the board defaults, set the speed to neutral

	def get_status(self):
		self.buttons = self.wii.state['buttons']
		self.status_button = not pi.read(button)

class wiimote_watcher(threading.Thread):
	""" A wiimote checking thread class """

	bluetooth_ping = ["sudo", "l2ping", "-c", "1", "-t", "1", wiimote_bluetooth]
		
	def run(self):
		while True:
			self.wiimote_check()
			time.sleep(0.1)

	def try_comms(self):
        	command = subprocess.Popen(wiimote_watcher.bluetooth_ping, stdout=subprocess.PIPE).communicate()[0]
        	return command

	def motor_off(self):
		global stop_val
		stop_val = True # Causes main thread loop to stop working and speed to default

	def shutdown(self):
		self.motor_off()
		if is_debug:
			print("OFF")
		else:
			subprocess.call(powerdown)

	def wiimote_check(self):
		try:
			output = self.try_comms()
			print(output)
			if (("100% loss") in output) or (output == ""): # If 100% packets lost: wiimote died. If output is null: bluetooth dongle died
				self.shutdown()
		except:
			self.shutdown()			

###

def main():
	
	# Class instance and program run
	skate = Skateboard()
	pi.write(led,1)		# DDD Note:  Remove later
	skate.blinky(12000,100)     # DDD Note:  skate.blinky(20,0.05)
#	skate.connection_process()
	# Wiimote checker thread
#	checker = wiimote_watcher()
#	checker.daemon = True
#	checker.start()
#	try:
#		skate.run_process()
#	except KeyboardInterrupt:
#		raise
#	except:
#		skate.speed = 1500
#		if is_debug:
#			raise
#		else:
#			subprocess.call(powerdown)

# if __name__ == "__main__":
	main()
