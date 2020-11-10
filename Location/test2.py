from PIL import Image
import matplotlib.pyplot as plt
from math import sqrt, sin, cos, atan, fabs, pi, e


def get_path_obstacle(rgb_map, x1, y1, x2, y2):
    rssi_subtract = 0
    dx = x2 - x1
    dy = y2 - y1
    px_distance = sqrt(dy ** 2 + dx ** 2)
    path_angle = fabs(atan(dy/dx)) if not dx == 0 else pi/2
    x_neg = dx < 0
    y_neg = dy < 0
    for path_distance in range(int(px_distance)):
        path_x = path_distance * cos(path_angle) * (-1 if x_neg else 1)
        path_y = path_distance * sin(path_angle) * (-1 if y_neg else 1)
        path_x = path_x + x1
        path_y = path_y + y1
        r, g, b = rgb_map.getpixel((path_x, path_y))
        if b - r > 30 and g - r > 30:
            rssi_subtract += 2
        elif r - g > 30 and r - b > 30:
            rssi_subtract += 8
        elif g - r > 30 and g - b > 30:
            rssi_subtract += 6
        elif b - r > 30 and b - g > 30:
            rssi_subtract += 4
    return rssi_subtract


def draw_heat_map(rssi_map, min_val, max_val, width, height):
    heat_map = Image.new("RGB", size=(width, height))
    pixels = heat_map.load()
    val_range = max_val - min_val
    for pos, val in rssi_map.items():
        x = pos[0]
        y = pos[1]
        colour_intensity = ((val - min_val) / val_range) * 255
        pixels[x, y] = (int(colour_intensity), 0, 0)
    plt.imshow(heat_map)
    plt.show()


def create_map(map_dir, ap_x, ap_y):
    obstacle_map = Image.open(map_dir)
    width, height = obstacle_map.size
    rgb_map = obstacle_map.convert("RGB")
    rssi_map = {}
    for x in range(width):
        for y in range(height):
            r, g, b = rgb_map.getpixel((x, y))
            if r == g == b == 0:
                rssi_map[(x, y)] = -1
                continue
            dy = x - ap_x
            dx = y - ap_y
            distance = sqrt(dy**2 + dx**2) / 10
            raw_rssi = e ** (-0.232584 * distance) * (87.4389 - 81 * e ** (0.232584 * distance))
            adjusted_rssi = raw_rssi - get_path_obstacle(rgb_map, x, y, ap_x, ap_y)
            rssi_map[(x, y)] = adjusted_rssi
    draw_heat_map(rssi_map, -90, -30, width, height)


create_map("maps/0.bmp", 50, 100)