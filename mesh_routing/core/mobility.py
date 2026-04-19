import numpy as np
import math
from typing import Dict
from core.node import Node

class RandomWaypointMobility:
    """Standard Random Waypoint mobility model."""
    def __init__(self, nodes: Dict[int, Node], config, rng: np.random.Generator):
        self.nodes = nodes
        self.config = config
        self.rng = rng

    def step(self, dt: float):
        for node in self.nodes.values():
            if node.pause_remaining > 0:
                node.pause_remaining -= dt
                continue

            dx = node.target_x - node.x
            dy = node.target_y - node.y
            dist = math.hypot(dx, dy)

            if dist < 0.1: # Reached target
                node.pause_remaining = self.config.pause_time
                node.target_x = self.rng.uniform(0, self.config.area_size)
                node.target_y = self.rng.uniform(0, self.config.area_size)
                speed = self.rng.uniform(self.config.min_speed, self.config.max_speed)
                if speed == 0:
                    node.vx = 0
                    node.vy = 0
                else:
                    angle = math.atan2(node.target_y - node.y, node.target_x - node.x)
                    node.vx = speed * math.cos(angle)
                    node.vy = speed * math.sin(angle)
            else:
                move_dist = min(dist, math.hypot(node.vx, node.vy) * dt)
                angle = math.atan2(dy, dx)
                node.x += move_dist * math.cos(angle)
                node.y += move_dist * math.sin(angle)
                
                # Boundary check
                node.x = max(0.0, min(self.config.area_size, node.x))
                node.y = max(0.0, min(self.config.area_size, node.y))


class GaussMarkovMobility:
    """Gauss-Markov mobility model."""
    def __init__(self, nodes: Dict[int, Node], config, rng: np.random.Generator, alpha: float = 0.5):
        self.nodes = nodes
        self.config = config
        self.rng = rng
        self.alpha = alpha
        self.speeds = {n.id: rng.uniform(config.min_speed, config.max_speed) for n in nodes.values()}
        self.angles = {n.id: rng.uniform(0, 2*math.pi) for n in nodes.values()}
        self.mean_speed = (config.min_speed + config.max_speed) / 2.0

    def step(self, dt: float):
        for node in self.nodes.values():
            # Update speed and angle
            s_rand = self.rng.normal(0, 1)
            a_rand = self.rng.normal(0, math.pi/4)
            
            self.speeds[node.id] = (self.alpha * self.speeds[node.id] + 
                                  (1 - self.alpha) * self.mean_speed + 
                                  math.sqrt(1 - self.alpha**2) * s_rand)
            self.angles[node.id] = (self.alpha * self.angles[node.id] + 
                                  (1 - self.alpha) * self.angles[node.id] + 
                                  math.sqrt(1 - self.alpha**2) * a_rand)
            
            speed = max(self.config.min_speed, min(self.config.max_speed, self.speeds[node.id]))
            
            node.vx = speed * math.cos(self.angles[node.id])
            node.vy = speed * math.sin(self.angles[node.id])
            
            node.x += node.vx * dt
            node.y += node.vy * dt
            
            # Bounce off walls
            if node.x < 0 or node.x > self.config.area_size:
                self.angles[node.id] = math.pi - self.angles[node.id]
                node.x = max(0.0, min(self.config.area_size, node.x))
            if node.y < 0 or node.y > self.config.area_size:
                self.angles[node.id] = -self.angles[node.id]
                node.y = max(0.0, min(self.config.area_size, node.y))
