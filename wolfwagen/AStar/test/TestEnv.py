import sys

sys.path.insert(0, '/home/sarvesh/Documents/GitHub/wolfwagen/AStar/environment')

import environment

sys.path.insert(1, '/home/sarvesh/Documents/GitHub/wolfwagen/AStar/robotAgent')
import robot

test = environment.Environment()

robotAgent = robot.Robot(test)

print(test.update_env())
print(test.positions)
print(test.roads)

print(test.get_neighbor_positions(test.positions[0][0]))