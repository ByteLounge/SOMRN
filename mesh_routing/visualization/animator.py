import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import matplotlib.patches as patches
from simulation.engine import SimulationEngine
from typing import Optional

class TopologyAnimator:
    """Creates a Matplotlib animation of the network simulation."""
    def __init__(self, engine: SimulationEngine):
        self.engine = engine
        self.fig, self.ax = plt.subplots(figsize=(8, 8))
        self.ax.set_xlim(0, engine.config.area_size)
        self.ax.set_ylim(0, engine.config.area_size)
        self.ax.set_title(f"Network Animation: {engine.protocol.name}")
        
        self.node_scatter = self.ax.scatter([], [], s=100, c='royalblue', zorder=5)
        self.edge_lines = []
        self.packet_dots = []
        self.time_text = self.ax.text(0.02, 0.95, '', transform=self.ax.transAxes)

    def _update(self, frame):
        # Run one step (or multiple for speed)
        steps_per_frame = 5
        for _ in range(steps_per_frame):
            self.engine.mobility.step(self.engine.config.time_step)
            self.engine.network.time += self.engine.config.time_step
            self.engine.network.update_links()
            # Simplified engine call for animation purposes
            # (In a real scenario we'd just hook into the engine's main loop)
        
        # Update node positions
        x = [n.x for n in self.engine.network.nodes.values()]
        y = [n.y for n in self.engine.network.nodes.values()]
        self.node_scatter.set_offsets(list(zip(x, y)))
        
        # Update edges
        for line in self.edge_lines:
            line.remove()
        self.edge_lines = []
        
        for u, v in self.engine.network.graph.edges():
            n1 = self.engine.network.nodes[u]
            n2 = self.engine.network.nodes[v]
            link = self.engine.network.get_link(u, v)
            q = link.quality if link else 0.0
            line, = self.ax.plot([n1.x, n2.x], [n1.y, n2.y], color=(1-q, q, 0, 0.5), zorder=1)
            self.edge_lines.append(line)
            
        self.time_text.set_text(f"Time: {self.engine.network.time:.1f}s")
        return [self.node_scatter, self.time_text] + self.edge_lines

    def animate(self, duration: float):
        n_frames = int(duration / (self.engine.config.time_step * 5))
        self.ani = FuncAnimation(self.fig, self._update, frames=n_frames, blit=True, interval=50)
        plt.show()

    def save_video(self, path: str):
        # Requires ffmpeg
        try:
            self.ani.save(path, writer='ffmpeg', fps=20)
        except Exception as e:
            print(f"Failed to save video: {e}. Ensure ffmpeg is installed.")
