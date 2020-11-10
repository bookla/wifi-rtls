import subprocess
import re
from PIL import Image, ImageDraw
import csv
from math import sqrt, pow, atan, fabs, sin, cos, pi, e
import pickle
from os import path
import matplotlib.pyplot as plt
import time
import statistics

known_aps = ["f4:2e:7f:78:c4:d4",
			 "44:67:47:76:fe:74",
			 "f8:38:80:e0:79:3f",
			 "10:7b:44:e8:4e:00",
			 "b4:18:d1:e0:37:36",
			 "74:da:38:85:e5:1a",
			 "d4:6e:0e:69:d3:36",
			 "e8:de:27:62:9e:c0",
			 "00:f7:6f:d1:48:bb",
			 "88:dc:96:7b:68:ac"]

ap_floor = {}

curve_strength = 780
d_shift = 9.0
min_rssi = 107
floor_thickness = 0.3*10


def get_path_obstacle(rgb_map, x1, y1, x2, y2):
	# RED: -12dB, GREEN: -8dB, BLUE: -4dB
	dx = x2 - x1
	dy = y2 - y1
	px_distance = sqrt(pow(dx, 2) + pow(dy, 2))
	path_angle = fabs(atan(dy/dx)) if not dx == 0 else pi/2
	x_neg = dx < 0
	y_neg = dy < 0
	sig_deg = 0
	# trace path
	for each_path_distance in range(int(px_distance)):
		x = (each_path_distance * cos(path_angle))
		y = (each_path_distance * sin(path_angle))
		x = (x * (-1) if x_neg else x) + x1
		y = (y * (-1) if y_neg else y) + y1
		r, g, b = rgb_map.getpixel((x, y))
		if more_than(b, r) and more_than(g, r):
			sig_deg += 2
		elif more_than(r, g) and more_than(r, b):
			sig_deg += 8
		elif more_than(g, r) and more_than(g, b):
			sig_deg += 6
		elif more_than(b, r) and more_than(b, g):
			sig_deg += 4

	return sig_deg


def more_than(x, y):
	return (x - y) > 60


def generate_map(ap_location_x, ap_location_y, ap_offset, obstacle_map):
	width, height = obstacle_map.size
	eq_format = "{0} + {1}*(log({2}))"
	expected_rssi_map = {}
	rgb_map = obstacle_map.convert("RGB")
	for x in range(width):
		for y in range(height):
			dx = fabs(x - ap_location_x)
			dy = fabs(y - ap_location_y)
			distance = sqrt(pow(dx, 2) + pow(dy, 2))/10
			if distance == 0:
				distance = 0.1
			#expected_rssi_eq = eq_format.format(str(-32.048412), str(-12.509812), str(distance))
			#raw_rssi = eval(expected_rssi_eq)
			raw_rssi = -67288.14 + (-0.8809523 - -67288.14) / (1 + pow(distance / 74577080000, 0.3082139))
			adjusted_rssi = raw_rssi - get_path_obstacle(rgb_map, x, y, ap_location_x, ap_location_y) + ap_offset
			expected_rssi_map[(x, y)] = adjusted_rssi
	return expected_rssi_map


def generate_heat_map(expected_rssi_map, min_strength, max_strength, ap_x, ap_y, save_name="temp"):
	heat_map = Image.new('RGB', size=(200, 150))
	pixels = heat_map.load()
	val_range = max_strength - min_strength
	if val_range <= 0:
		raise ValueError("Minimum value cannot be smaller or equals to maximum value")
	for pos, val in expected_rssi_map.items():
		x = pos[0]
		y = pos[1]
		colour_intensity = ((val - min_strength)/val_range)*255
		pixels[x, y] = (int(colour_intensity), 0, 0)
	pixels[ap_x, ap_y] = (0, 100, 255)
	plt.imshow(heat_map)
	plt.show()
	heat_map.save(save_name + ".png", "PNG")


def read_create_ap_data():
	global ap_floor
	ap_maps = {}
	with open("ap_data.csv", "r") as csv_file:
		ap_list = csv.reader(csv_file, delimiter=',')
		for each_ap in ap_list:
			ap_mac = each_ap[0]
			print("Generating Map for " + ap_mac)
			ap_x = int(each_ap[1])
			ap_y = int(each_ap[2])
			ap_gain = int(each_ap[3])
			floor = int(each_ap[4])
			ap_floor[ap_mac] = floor
			floor_map = path.join("maps", str(floor) + ".bmp")
			obstacle_map = Image.open(floor_map)
			arr_map = generate_map(ap_x, ap_y, ap_gain, obstacle_map)
			ap_maps[ap_mac] = arr_map
			generate_heat_map(arr_map, -100, -20, ap_x, ap_y, ap_mac.replace(":", "-"))
	return ap_maps


def index_from_rssi(rssi):
	a = 25000
	b = 136
	c = 170
	return a/(int(rssi) - b) + c


def get_probability(aps_list, aps_maps, floor_map, floor, power=2.5):
	width, height = floor_map.size
	scores = {}
	fallback_scores = {}
	ap_to_calculate = sum(1 for el in aps_maps.keys() if el in aps_list.keys() and int(ap_floor[el]) == floor)
	if ap_to_calculate == 0:
		return {}, 0
	print(ap_to_calculate)
	print(aps_maps.keys())
	print(aps_list.keys())
	max_score = 64
	for x in range(width):
		for y in range(height):
			pos_score = 0
			fallback_pos = 0
			for ap_mac, each_map in aps_maps.items():
				if ap_mac in aps_list.keys() and int(ap_floor[ap_mac]) == floor:
					actual_reading = aps_list[ap_mac]
					predicted_reading = each_map[(x, y)]
					d_index = fabs(index_from_rssi(actual_reading) - index_from_rssi(predicted_reading))
					pos_score += max_score - pow(d_index, power)
					fallback_pos += max_score - pow(d_index, 1.9)
			scores[(x, y)] = pos_score/ap_to_calculate
			fallback_scores[(x, y)] = fallback_pos/ap_to_calculate
	return scores, fallback_scores, max_score


def get_average_point(x_list, y_list):
	if len(x_list) == 0 or len(y_list) == 0:
		return 0, 0, 0
	sum_x = sum(x_list)
	sum_y = sum(y_list)
	avg_x = sum_x/len(x_list)
	avg_y = sum_y/len(y_list)
	x_std = statistics.pstdev(x_list)
	y_std = statistics.pstdev(y_list)
	std_dev = (x_std + y_std)/2
	return avg_x, avg_y, std_dev*1.5


def draw_probability_map(scores, fallback_score, max_score, base_map):
	prob_map = base_map.convert("RGB")
	pixels = prob_map.load()
	x_list = []
	y_list = []
	x_list_lp = []
	y_list_lp = []
	for pos, score in scores.items():
		x = pos[0]
		y = pos[1]
		colour_intensity = (score/max_score)*255
		weight = 0
		if 30 <= colour_intensity < 70:
			weight = 1
		elif 70 <= colour_intensity < 110:
			weight = 2
		elif 110 <= colour_intensity < 150:
			weight = 3
		elif 150 <= colour_intensity < 190:
			weight = 4
		elif colour_intensity > 190:
			weight = 5
		elif colour_intensity > 4:
			x_list_lp.append(x)
			y_list_lp.append(y)
		if colour_intensity < 30:
			continue
		for i in range(weight):
			x_list.append(x)
			y_list.append(y)
		pixels[x, y] = (0, int(colour_intensity), 0)
	draw = ImageDraw.Draw(prob_map, "RGBA")
	if len(x_list_lp) == 0 or len(y_list_lp) == 0:
		for pos, score in fallback_score.items():
			x = pos[0]
			y = pos[1]
			colour_intensity = (score / max_score) * 255
			weight = 0
			if 30 <= colour_intensity < 70:
				weight = 1
			elif 70 <= colour_intensity < 110:
				weight = 2
			elif 110 <= colour_intensity < 150:
				weight = 3
			elif 150 <= colour_intensity < 190:
				weight = 4
			elif colour_intensity > 190:
				weight = 5
			elif colour_intensity > 4:
				x_list_lp.append(x)
				y_list_lp.append(y)
			if colour_intensity < 30:
				continue
			for i in range(weight):
				x_list.append(x)
				y_list.append(y)
			pixels[x, y] = (0, int(colour_intensity), 0)
		text_low_acc = "Low Accuracy Fallback"
		draw.text((10, 0), text_low_acc, fill="black")
	if len(x_list) == 0 or len(y_list) == 0:
		average_x, average_y, st_dev = get_average_point(x_list_lp, y_list_lp)
	else:
		average_x, average_y, st_dev = get_average_point(x_list, y_list)
	# Draw Accuracy Indicator
	accuracy_radius = st_dev
	accuracy_circle = (average_x - accuracy_radius, average_y - accuracy_radius, average_x + accuracy_radius, average_y + accuracy_radius)
	draw.ellipse(accuracy_circle, fill=(186, 255, 237, 120), outline=(0, 0, 0, 0))
	# Draw Position
	position_radius = 3
	position_circle = (average_x - position_radius, average_y - position_radius, average_x + position_radius, average_y + position_radius)
	draw.ellipse(position_circle, fill=(0, 204, 255), outline=(255, 255, 255))
	# Draw Accuracy Text
	text = "Accuracy : " + str(round(st_dev)/10) + "m"
	draw.text((10, 140), text, fill="black")
	# Show Image
	plt.imshow(prob_map)
	plt.show()


def main(aps_maps, floor_map, floor):
	print("Locating...")
	aps_list = get_aps(silent=False, filter_known=True)
	scores, fallback_score, max_score = get_probability(aps_list, aps_maps, floor_map, floor)
	draw_probability_map(scores, fallback_score, max_score, floor_map)


def get_aps(silent=True, filter_known=False):
	scan_cmd = subprocess.Popen(['airport', '-s'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	scan_out, scan_err = scan_cmd.communicate()
	split_data = str(scan_out).split(" ")
	aps_found = {}
	latest_ap = ""
	for each_data in split_data:
		mac_format = re.compile('.{2}:.{2}:.{2}:.{2}:.{2}:.{2}')
		if mac_format.match(each_data) is not None:
			latest_ap = each_data
		rssi_format = re.compile('-.{2}')
		if rssi_format.match(each_data) is not None:
			aps_found[latest_ap] = each_data
	filtered_ap = {}
	if filter_known:
		for ap_mac, rssi in aps_found.items():
			if ap_mac in known_aps:
				filtered_ap[ap_mac] = rssi
	else:
		filtered_ap = aps_found
	if len(filtered_ap) == 0:
		# raise Exception("No known AP found")
		time.sleep(3)
		return {}
	if not silent:
		cur_cmd = subprocess.Popen(['airport', '-I'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		cur_out, cur_err = cur_cmd.communicate()
		cur_ap = str(cur_out).split("\\n")[11][-17:]
		for ap_mac in sorted(filtered_ap.keys()):
			print("Found " + ap_mac + ", RSSI: " + aps_found[ap_mac] + "dB", end="")
			if ap_mac == cur_ap:
				print(" (Connected)")
			elif ap_mac not in known_aps:
				print(" (Unknown)")
			else:
				print()
	return filtered_ap


def read_floor_data():
	global ap_floor
	with open("ap_data.csv", "r") as csv_file:
		ap_list = csv.reader(csv_file, delimiter=',')
		for each_ap in ap_list:
			ap_mac = each_ap[0]
			floor = each_ap[4]
			ap_floor[ap_mac] = floor


def locate():
	f = open('maps.pckl', 'rb')
	obj = pickle.load(f)
	f.close()
	while True:
		for each_floor in range(1):
			read_floor_data()
			floor_map = path.join("maps", str(each_floor) + ".bmp")
			main(obj, Image.open(floor_map), each_floor)


def create_and_save_maps():
	signal_maps = read_create_ap_data()
	f = open('maps.pckl', 'wb')
	pickle.dump(signal_maps, f)
	f.close()


create_and_save_maps()
locate()
