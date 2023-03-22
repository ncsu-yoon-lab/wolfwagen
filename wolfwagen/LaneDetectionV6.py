#!/usr/bin/env python
import rclpy # Python Client Library for ROS 2
from rclpy.node import Node # Handles the creation of nodes
from sensor_msgs.msg import Image # Image is the message type
from std_msgs.msg import Int64
from cv_bridge import CvBridge # Package to convert between ROS and OpenCV Images
import cv2 as cv # OpenCV library
import numpy as np
import time
import math
import random
import threading
from geometry_msgs.msg import PoseStamped

# Set it to 'False' when driving (True when debugging)
SHOW_IMAGES = False

DRAW_LINE_IMG = True


DOT_COLOR = [61, 217, 108]
DOT_SIZE = 5

LINE_COLOR = (255, 0, 0)
LINE_THICKNESS = 2

# LANE_COLOR = (0, 0, 255)
LANE_COLOR = (255, 255, 0)
LANE_THICKNESS = 5

LANE_REGION_COLOR = (0, 255, 0)
LANE_CENTER_COLOR = (0, 0, 255)

CAR_CENTER_COLOR = (180, 180, 0)

#GAP_THRESHOLD = 


CAMERA_TOPIC_NAME = '/zed2i/zed_node/stereo/image_rect_color'
# '/zed2i/zed_node/rgb_raw/image_raw_color'	

# Original image fram
frame = None

last_frame_time = time.time()
br = CvBridge()
def listener_callback(msg):
	global frame, last_frame_time
	frame = br.imgmsg_to_cv2(msg)
	last_frame_time = time.time()



last_turn_time = time.time()

pose = None
def pose_callback(data):
	global pose
	pose = data

"""
Convert a quaternion into euler angles (roll, pitch, yaw)
roll is rotation around x in radians (counterclockwise)
pitch is rotation around y in radians (counterclockwise)
yaw is rotation around z in radians (counterclockwise)
"""
def euler_from_quaternion(quat):
	x = quat.x
	y = quat.y
	z = quat.z
	w = quat.w
	t0 = +2.0 * (w * x + y * z)
	t1 = +1.0 - 2.0 * (x * x + y * y)
	roll_x = math.atan2(t0, t1)

	t2 = +2.0 * (w * y - z * x)
	t2 = +1.0 if t2 > +1.0 else t2
	t2 = -1.0 if t2 < -1.0 else t2
	pitch_y = math.asin(t2)

	t3 = +2.0 * (w * z + x * y)
	t4 = +1.0 - 2.0 * (y * y + z * z)
	yaw_z = math.atan2(t3, t4)

	return roll_x, pitch_y, yaw_z # in radians



# Use this if image is too dark
def adjust_gamma(image, gamma=1.0):
    invGamma = 1.0 / gamma
    table = np.array([((i / 255.0) ** invGamma) * 255
        for i in np.arange(0, 256)]).astype("uint8")
    return cv.LUT(image, table)


def get_end_points(rho, theta):
	# Note: cv.HoughLines return the <rho, theta> of each lines
	a = math.cos(theta)
	b = math.sin(theta)
	x0 = a * rho
	y0 = b * rho

	x1 = int(x0 + 1000*(-b))
	y1 = int(y0 + 1000*(a))
	x2 = int(x0 - 1000*(-b))
	y2 = int(y0 - 1000*(a))

	return x1, y1, x2, y2

def crop(image, width, height):
	# Assume: image is a stereo image (=left cam + right cam) from the zed camera
	
	# center-cut_width : center+cut_width will be deleted
	# if not stereo image, comment out this block
	center = int(width/2)
	cut_width = int(width/4)
	image = np.delete(image, slice(center-cut_width, center+cut_width), 1)	
	
	# cut top half
	image = image[int(height/2) : height-1, :]
	
	return image

	
def process_img(frame):
	global last_turn_time

	org_color_frame = frame

	img = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
	
	# frame = adjust_gamma(frame, 1)

	height, width = img.shape	#720, 2560
	img = crop(img,width,height)	
	cropped_color_frame = crop(org_color_frame,width,height)
		
	height, width = img.shape	#cropped

	if SHOW_IMAGES:
		cv.imshow('cropped', img)
		cv.waitKey(1)
		
	# remove noise
	kernel_size = 7
	img = cv.GaussianBlur(img, (kernel_size, kernel_size), 0)

	# thresholding. If seeing some noise, increase the lower threshold
	_, img = cv.threshold(img, 160, 255, cv.THRESH_BINARY)

	# Canny Edge Detection
	edge = cv.Canny(img, 70, 200 ) # you can adjust these min/max values

	# Edges could be too thin (which could make it difficult for Hough Transform to detect lines)
	# So, make the edges thicker
	kernel = cv.getStructuringElement(cv.MORPH_RECT, (3,3))
	edge = cv.dilate(edge, kernel, iterations=1)
		
	if SHOW_IMAGES:
		cv.imshow('canny', edge)
		cv.waitKey(1)
	
	# for intersection
	left_crop = edge[170 :, : 300]
	right_crop = edge[170 : , 900 :]

	# cv.imshow("left_turn" , left_crop)
	# cv.waitKey(1)

	# cv.imshow("right_turn" , right_crop)
	# cv.waitKey(1)
	

	if (time.time() - last_turn_time > 5):
		# If it hasn't been more than 5 seconds since we did the last turning, don't check the following conditions

		is_at_intersection = 0	

		if left_crop.sum() < 1000:
			print("left is open")
			is_at_intersection = 1			

		if right_crop.sum() < 1000:
			print("right is open")
			is_at_intersection += 2			

		turning_direction = 0

		if is_at_intersection > 0:
			#We start a turn

			turning = True
			if is_at_intersection == 1:
				turning_direction = 1	# left
			elif is_at_intersection == 2:
				turning_direction = 2	# right
			else:
				#both left and right are open
				turning_direction = random.randint(1,2)
			
			print("turning direction: ", turning_direction)
			last_turn_time = time.time()

			return (cropped_color_frame, 0, turning_direction)




	# # Probabilistic Hough Transform
	# rho = 1
	# theta = 1*np.pi/180.0
	# threshold = 15
	# minLineLength = 30   #The minimum number of points that can form a line. Lines with less than this number of points are disregarded.
	# maxLineGap = 20      #The maximum gap between two points to be considered in the same line.
	# lines = cv.HoughLinesP(edge, rho, theta, threshold, minLineLength, maxLineGap)



	# Non-probabilistic Hough Transform (works better)
	lines = cv.HoughLines(edge, 1, np.pi/180, 150, None, 0, 0)
		
	

	# Cross Track Error	
	CTE = 0
	
	if lines is None: 
		print("No lines detected")
		final = cropped_color_frame
		CTE = 0		
	else:
		left_line_x = []    #x-values of left lines 
		left_line_y = []    #y-values of left lines 
		right_line_x = []   #x-values of right lines 
		right_line_y = []   #y-values of right lines

		cnt_left = 0    # number of left lines
		cnt_right = 0   # number of right lines

		if DRAW_LINE_IMG:					
			line_image = np.copy(cropped_color_frame)*0

		for line in lines:

			# Note: we are using the standard Hough Transform, not the probabilistic version			
			rho = line[0][0]
			theta = line[0][1]
			x1, y1, x2, y2 = get_end_points(rho, theta)
			
			# for x1, y1, x2, y2 in line:	
			if True:
				
				if x2 - x1 == 0:
					continue

				slope = (y2 - y1) / float(x2 - x1)
				slope_threshold = 0.2
				if abs(slope) < slope_threshold:
					#print("slope %f is excluded" % slope)
					continue

				# line_len = np.sqrt( (x2-x1)**2 + (y2-y1)**2 )
				# line_len_threshold = 10
				# if line_len < line_len_threshold:
				# 	print("line len %f is too short" % line_len)
				# 	continue

				if DRAW_LINE_IMG:										
					cv.line(line_image, (x1, y1), (x2, y2), LINE_COLOR, LINE_THICKNESS)
					cv.circle(line_image, (x1, y1), DOT_SIZE, DOT_COLOR, -1)
					cv.circle(line_image, (x2, y2), DOT_SIZE, DOT_COLOR, -1)
		
				if slope <= 0:
					left_line_x.extend([x1, x2])
					left_line_y.extend([y1, y2])					
					cnt_left += 1										
				else:
					right_line_x.extend([x1, x2])
					right_line_y.extend([y1, y2])					
					cnt_right += 1
		
		
			
		MIN_Y = 0	# <-- top of lane markings
		MAX_Y = img.shape[0] # <-- bottom of lane markings

		left_polyfit = None
		right_polyfit = None

		print("cnt_left, cnt_right = ", cnt_left, cnt_right)
		
		if cnt_left > 0:
			#do 1D fitting
			left_polyfit = np.polyfit(left_line_y, left_line_x, deg=1)
			poly_left = np.poly1d(left_polyfit)
			left_x_start = int(poly_left(MAX_Y))
			left_x_end = int(poly_left(MIN_Y))
			
			if DRAW_LINE_IMG:
				cv.line(line_image, (left_x_start, MAX_Y), (left_x_end, MIN_Y), LANE_COLOR, LANE_THICKNESS)
			

		if cnt_right > 0:
			#do 1D fitting                
			right_polyfit = np.polyfit(right_line_y, right_line_x, deg=1)
			poly_right = np.poly1d(right_polyfit)
			right_x_start = int(poly_right(MAX_Y))
			right_x_end = int(poly_right(MIN_Y))
			
			if DRAW_LINE_IMG:
				cv.line(line_image, (right_x_start, MAX_Y), (right_x_end, MIN_Y), LANE_COLOR, LANE_THICKNESS)

		
		car_center = int(img.shape[1]/2)	#center of camera

		if cnt_left>0 and cnt_right>0:
			# Find CTE
			lane_center = (right_x_start+left_x_start)/2
			CTE = car_center - lane_center			
			
			if DRAW_LINE_IMG:
				cv.line(line_image, ( int((left_x_start+right_x_start)/2), MAX_Y), ( int((left_x_end + right_x_end)/2), MIN_Y), LANE_CENTER_COLOR, 5)
				cv.line(line_image, (car_center, MAX_Y), (car_center, MIN_Y), (255,255,0), 3)
				
				#Draw lane region
				mask = np.zeros_like(line_image)				
				vertices = np.array([[(left_x_start+10,MAX_Y),(left_x_end+10, MIN_Y), (right_x_end-10, MIN_Y), (right_x_start-10, MAX_Y)]], dtype=np.int32)
				cv.fillPoly(mask, vertices, LANE_REGION_COLOR)

				line_image = cv.addWeighted(line_image, 0.8, mask, 0.2, 0)				

		elif cnt_left+cnt_right == 0:
			CTE = 0
			print('cannot find any lane markings')
		else:
			if cnt_left==0:
				CTE = 500
				print('cannot find left lane marking')
			else:
				CTE = -500
				print('cannot find right lane marking')


		final = cropped_color_frame
		if DRAW_LINE_IMG:
			final = cv.addWeighted(final, 1, line_image, 1, 0)
		

	return (final, CTE, 0)

def main(args=None):
		
	rclpy.init(args=args)
	node = Node("Lane_detection_node")
	print("Lane_detection_node")
    
	img_subscription = node.create_subscription(
			Image,
			CAMERA_TOPIC_NAME,
			listener_callback,
			5)
	
	pose_subscription = node.create_subscription(
			PoseStamped,
			"/zed2i/zed_node/pose",
			pose_callback,
			20)
		
	lane_img_publisher = node.create_publisher(Image, 'lane_img', 1)
	pid_steering_publisher = node.create_publisher(Int64, 'pid_steering', 1)

	thread = threading.Thread(target=rclpy.spin, args=(node, ), daemon=True)
	thread.start()

	FREQ = 20	
	rate = node.create_rate(FREQ, node.get_clock())

	# For PID control	
	prev_error = 0
	Kp = 0.15	
	Ki = 0.0
	Kd = 0.01
	dt = 1/float(FREQ)
	integral = 0
	
	turning = False	#Am i making a turn (left or right)?
	turning_direction = 0	#1: left, 2: right
	yaw_target = 0
	
	left_turn_cmd = -100	
	right_turn_cmd = +100
	
	while rclpy.ok():
		if frame is not None and pose is not None:
			print("-----")

			if time.time() - last_frame_time > 3:
				print("NOT RECEIVING CAMERA DATA. ")
				break
		
			quat = pose.pose.orientation
			roll, pitch, yaw_now = euler_from_quaternion(quat)

			yaw_now = yaw_now * 180.0 / np.pi
			if (yaw_now < 0):
				yaw_now += 360.0

			print('yaw_now = ', yaw_now)
			
			if turning is True and time.time() - last_turn_time > 3.0:
				turning = False
				yaw_target = 0
				prev_error = 0

			if turning is True:
				#Already in the turning mode
				#Check if we need to stop or continue

				diff_yaw = math.fabs(yaw_now - yaw_target)
				# print("yaw_now = %f, yaw_target = %f, diff = %f" % (yaw_now, yaw_target, diff_yaw))

				if (diff_yaw < 15.0):
					#angle to the target yaw is small enough, so stop the turn
					turning = False
					yaw_target = 0
					prev_error = 0	#to reset the pid controller

					print("Turning is done")

				else:
					#just keep turning						
					print("Still turning")

					if turning_direction == 1:
						#left turn
						steering_cmd = left_turn_cmd
					elif turning_direction == 2:
						#right turn
						steering_cmd = right_turn_cmd
					else:
						print("CANNOT HAPPEN")
						steering_cmd = 0

				# just for streaming camera data -- nothing more
				final_image = crop(frame,frame.shape[1],frame.shape[0])

			else:
				#Not in the turning mode
				#Check if we need to start a turning or not
				
				final_image, CTE, turning_direction = process_img(frame)
				
				if turning_direction > 0:

					if turning is False:
						# now we start making a turn
						turning = True
						yaw_target = 0

						if turning_direction == 1:
							# left turn --> yaw increases
							yaw_target = yaw_now + 90 
							yaw_target = yaw_target % 360
							steering_cmd = left_turn_cmd							

						elif turning_direction == 2:
							# right turn --> yaw decreases

							yaw_target = yaw_now - 90
							yaw_target = yaw_target % 360
							steering_cmd = right_turn_cmd
			
				else:
					# Straight
					####### PID control
					setpoint = 0    #always want to stay on the center line
					error = setpoint - CTE
					integral = integral + error * dt
					derivative = (error - prev_error) / dt
					steering_cmd = Kp * error + Ki * integral + Kd * derivative
					prev_error = error

					print("CTE=", CTE)					
					
			if SHOW_IMAGES:
				cv.imshow('Lane following', final_image)
				cv.waitKey(1)

			
			#publish steering command
			m = Int64()
			m.data = int(steering_cmd)
			pid_steering_publisher.publish(m)

			print("steering_cmd = ", steering_cmd)

			# Lane image for rviz2 or webviz
			img_msg = br.cv2_to_imgmsg(final_image, encoding="bgra8")
			lane_img_publisher.publish(img_msg)
			
		rate.sleep()

	
	# Destroy the node explicitly
    # (optional - otherwise it will be done automatically
    # when the garbage collector destroys the node object)
	node.destroy_node()
	rclpy.shutdown()

if __name__ == '__main__':
    main()
