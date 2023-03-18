import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy
from std_msgs.msg import String
from std_msgs.msg import Int64
import struct
import can
import os
import threading

#os.system('sudo ip link set can0 up type can bitrate 250000')

in_min = -100
in_max = +100
out_min = 6554
out_max = 13108

throttle = 0
steer = 0
mode = 0

pid_steer = 0	#TODO: change name to audo_steer

auto_throttle = 0	#published (and controller) by xbox_controller	

def pwm(val):
	#TODO: input range check
	return (val - in_min) * (out_max - out_min) // (in_max - in_min) + out_min


def mode_switch_callback(data):
	global mode
	if mode != data.data:
		mode = data.data
		print("mode switched")
		
def manual_steering_callback(data):
	global steer
	steer = data.data

def manual_throttle_callback(data):
	global throttle
	throttle = data.data

def auto_throttle_callback(data):
	global auto_throttle
	auto_throttle = data.data

def pid_steering_callback(data):
	global pid_steer

	steer = data.data
	if steer > 100:
		steer = 100
	elif steer < -100:
		steer = -100
	if (steer==100):
			steer = 99
	
	pid_steer = steer
	



def main(args=None):
	print("Driver node")
	rclpy.init(args=args)
	node = Node("Drive_node")

	try:
		bus = can.interface.Bus(bustype='socketcan', channel='can0', bitrate=250000)
		print ("Opened CAN bus")
	except IOError:
		print ("Cannot open CAN bus")
		return 
	
	subscription_manual_steering = node.create_subscription(Int64,'manual_steering', manual_steering_callback, 1)
	subscription_manual_throttle = node.create_subscription(Int64,'manual_throttle', manual_throttle_callback, 1)
	subscription_auto_throttle = node.create_subscription(Int64,'auto_throttle', auto_throttle_callback, 1)
	subscription_mode_switch = node.create_subscription(Int64 , "mode_switch" , mode_switch_callback , 1)	
	subscription_pid_steering = node.create_subscription(Int64 , 'pid_steering' , pid_steering_callback , 1)

	thread = threading.Thread(target=rclpy.spin, args=(node, ), daemon=True)
	thread.start()

	rate = node.create_rate(20, node.get_clock())
	
	while rclpy.ok():
		
		if mode == 0:
			pwm_throttle = pwm(throttle)
			pwm_steer = pwm(steer)
		else:
			pwm_throttle = pwm(auto_throttle)
			pwm_steer = pwm(pid_steer)
		
		print("mode: %s, throttle: %d (auto: %d), steering: %d (auto: %d)" % ("Manual" if mode == 0 else "Auto", throttle, auto_throttle, steer, pid_steer))

				
		
		can_data = struct.pack('>hhI', pwm_throttle, pwm_steer, 0)
		new_msg = can.Message(arbitration_id=0x1,data=can_data, is_extended_id = False)
		bus.send(new_msg)

		rate.sleep()

	rclpy.spin(node)
	rclpy.shutdown()

if __name__ == '__main__':
	main()
