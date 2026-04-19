import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import networkx as nx
from typing import List
import numpy as np

class TopologyAnimator:
    def __init__(self, engine):
        self.engine = engine
        self.fig, self.ax = plt.subplots(figsize=(10, 10))
        self.config = engine.config
        
        self.nodes_scatter = None
        self.edges_lines = []
        self.packet_scatter = None
        
        self.history = []

    def _setup_plot(self):
        self.ax.set_xlim(0, self.config.area_size)
        self.ax.set_ylim(0, self.config.area_size)
        self.ax.set_title("Wireless Mesh Network Topology")
        self.ax.grid(True)

    def _update_frame(self, frame):
        self.ax.clear()
        self._setup_plot()
        
        snap = self.history[frame]
        nodes = snap['nodes']
        edges = snap['edges']
        
        # Plot nodes
        nx_coords = [n['x'] for n in nodes]
        ny_coords = [n['y'] for n in nodes]
        self.ax.scatter(nx_coords, ny_coords, c='blue', s=100, zorder=5)
        
        # Labels
        for n in nodes:
            self.ax.annotate(str(n['id']), (n['x'], n['y']), xytext=(5, 5), textcoords='offset points')
            
        # Plot edges
        node_pos = {n['id']: (n['x'], n['y']) for n in nodes}
        for e in edges:
            u, v = e['source'], e['target']
            x_vals = [node_pos[u][0], node_pos[v][0]]
            y_vals = [node_pos[u][1], node_pos[v][1]]
            self.ax.plot(x_vals, y_vals, c='gray', alpha=0.5, zorder=1)

    def animate(self, duration: float):
        self.engine.on_snapshot = self._record_snapshot
        
        # Run simulation to collect history
        print("Running simulation to collect animation frames...")
        self.engine.run()
        
        print("Generating animation...")
        anim = FuncAnimation(self.fig, self._update_frame, frames=len(self.history), interval=200)
        plt.show()

    def _record_snapshot(self, t, metrics):
        self.history.append(self.engine.get_topology_for_dashboard())

    def save_video(self, path: str):
        self.engine.on_snapshot = self._record_snapshot
        print("Running simulation to collect video frames...")
        self.engine.run()
        
        print(f"Saving animation to {path}...")
        anim = FuncAnimation(self.fig, self._update_frame, frames=len(self.history), interval=200)
        anim.save(path, writer='ffmpeg', fps=10)
        print("Video saved.")
