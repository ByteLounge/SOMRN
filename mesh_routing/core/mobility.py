import numpy as np
from typing import List, Dict
from core.node import Node
from config import SimConfig

class RandomWaypointMobility:
    """Implements the Random Waypoint mobility model."""
    def __init__(self, nodes: List[Node], config: SimConfig):
        self.nodes = nodes
        self.config = config
        self.rng = np.random.default_rng(config.seed)
        
        for node in self.nodes:
            self._set_new_waypoint(node)

    def _set_new_waypoint(self, node: Node):
        """Pick a new random target and speed for the node."""
        node.target_x = self.rng.uniform(0, self.config.area_size)
        node.target_y = self.rng.uniform(0, self.config.area_size)
        
        if self.config.max_speed > self.config.min_speed:
            speed = self.rng.uniform(self.config.min_speed, self.config.max_speed)
        else:
            speed = self.config.max_speed
            
        dist = node.distance_to(Node(-1, node.target_x, node.target_y, self.config))
        if dist > 0:
            node.vx = ((node.target_x - node.x) / dist) * speed
            node.vy = ((node.target_y - node.y) / dist) * speed
        else:
            node.vx = 0
            node.vy = 0
            
        node.pause_remaining = self.config.pause_time

    def step(self, dt: float):
        """Move all nodes by one time step."""
        for node in self.nodes:
            if node.pause_remaining > 0:
                node.pause_remaining -= dt
                continue
                
            dist_to_target = node.distance_to(Node(-1, node.target_x, node.target_y, self.config))
            move_dist = np.sqrt(node.vx**2 + node.vy**2) * dt
            
            if move_dist >= dist_to_target:
                node.x = node.target_x
                node.y = node.target_y
                self._set_new_waypoint(node)
            else:
                node.x += node.vx * dt
                node.y += node.vy * dt


class GaussMarkovMobility:
    """Implements the Gauss-Markov mobility model for smoother movement."""
    def __init__(self, nodes: List[Node], config: SimConfig, alpha: float = 0.75):
        self.nodes = nodes
        self.config = config
        self.alpha = alpha
        self.rng = np.random.default_rng(config.seed)
        
        # Initialize velocities
        for node in self.nodes:
            angle = self.rng.uniform(0, 2 * np.pi)
            speed = self.rng.uniform(config.min_speed, config.max_speed)
            node.vx = speed * np.cos(angle)
            node.vy = speed * np.sin(angle)

    def step(self, dt: float):
        """Move all nodes by one time step using Gauss-Markov process."""
        mean_speed = (self.config.max_speed + self.config.min_speed) / 2.0
        
        for node in self.nodes:
            # Update velocities based on previous state and randomness
            node.vx = (self.alpha * node.vx + 
                       (1 - self.alpha) * mean_speed + 
                       np.sqrt(1 - self.alpha**2) * self.rng.normal(0, 1))
            
            node.vy = (self.alpha * node.vy + 
                       (1 - self.alpha) * mean_speed + 
                       np.sqrt(1 - self.alpha**2) * self.rng.normal(0, 1))
            
            # Normalize speed to be within [min_speed, max_speed]
            speed = np.sqrt(node.vx**2 + node.vy**2)
            if speed > self.config.max_speed:
                node.vx = (node.vx / speed) * self.config.max_speed
                node.vy = (node.vy / speed) * self.config.max_speed
            elif speed < self.config.min_speed and speed > 0:
                node.vx = (node.vx / speed) * self.config.min_speed
                node.vy = (node.vy / speed) * self.config.min_speed
                
            # Update positions
            new_x = node.x + node.vx * dt
            new_y = node.y + node.vy * dt
            
            # Boundary handling (bounce back)
            if new_x < 0 or new_x > self.config.area_size:
                node.vx = -node.vx
                new_x = max(0, min(self.config.area_size, new_x))
            if new_y < 0 or new_y > self.config.area_size:
                node.vy = -node.vy
                new_y = max(0, min(self.config.area_size, new_y))
                
            node.x = new_x
            node.y = new_y
