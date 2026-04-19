# Self-Optimizing Wireless Mesh Networks: A Reinforcement Learning Approach

**Author:** Yash Sanikop  
**Project Repository:** [https://github.com/ByteLounge/SOMRN](https://github.com/ByteLounge/SOMRN)  
**Date:** April 2026

---

## 1. Abstract
Wireless Mesh Networks (WMNs) are fundamental to modern emergency response, rural connectivity, and industrial IoT. However, traditional routing protocols often struggle with the dynamic nature of these networks, such as moving nodes and fluctuating traffic congestion. This paper introduces a self-optimizing framework and a novel Reinforcement Learning (RL) protocol named **Congestion-Predictive Q-Routing (CPQR)**. Our approach allows nodes to learn optimal routing paths autonomously based on environmental feedback. We also present a high-fidelity simulator with a Cisco-inspired dashboard to visualize these complex interactions in real-time.

---

## 2. Introduction
In a Wireless Mesh Network, nodes (routers) are connected wirelessly and must collaborate to forward data packets across the network. Unlike fixed infrastructure, WMNs are often "ad-hoc," meaning nodes can move, fail, or join the network at any time.

### The Challenge
Most traditional protocols are either:
- **Reactive (like AODV):** They only find a route when needed, which causes delays during initial connection.
- **Proactive (like OLSR):** They constantly map the whole network, which wastes battery and bandwidth on background "chatter."

Neither approach handles **congestion** (traffic jams) or **mobility** (nodes moving out of range) perfectly. When a node becomes congested, traditional protocols keep sending data to it until the link breaks. When a node moves, the path is lost, and the network must "re-learn" everything from scratch.

---

## 3. Problem Statement
The primary problem addressed in this research is the **lack of adaptability** in standard routing protocols. In a dynamic mesh network, a "good" path at 10:00 AM might be a "bad" path at 10:01 AM due to:
1.  **Traffic Bursts:** A specific node being overwhelmed by packets.
2.  **Node Mobility:** The physical distance between nodes changing, weakening the signal.
3.  **Energy Depletion:** Nodes running out of battery, causing network partitions.

---

## 4. The Proposed Approach: CPQR
Our solution, **Congestion-Predictive Q-Routing (CPQR)**, treats every node in the network as an intelligent agent.

### 4.1 How it Works: Q-Learning
CPQR uses a branch of AI called Reinforcement Learning. Each node maintains a "Q-Table"—a brain that stores a score for every possible next-hop neighbor.
- If a path leads to a fast delivery, the score improves (Reward).
- If a path leads to a drop or a long delay, the score decreases (Penalty).

### 4.2 The Multi-Objective Reward Function
Unlike standard Q-routing which only looks at delay, CPQR calculates a reward ($R$) based on three factors:
1.  **Latency:** How long the packet took to travel.
2.  **Congestion Penalty:** Is the next node's queue almost full?
3.  **Energy Cost:** Does the next node have enough battery?

Mathematically, the update follows the Bellman Equation:
$$Q(u, d, v) \leftarrow (1 - \alpha) Q(u, d, v) + \alpha \left[ R + \gamma \min_{v'} Q(v, d, v') \right]$$

### 4.3 Link Lifetime Prediction (LLT)
To handle mobility, CPQR tracks the Signal Strength (RSSI) trends. If the signal to a neighbor is dropping rapidly, CPQR predicts the **Link Lifetime**. If the link is expected to break in less than a few seconds, the agent proactively switches to a safer, more stable route before the break even happens.

---

## 5. Simulator Features
To validate CPQR, we developed a custom simulation environment with several advanced features:

### 5.1 Professional Visualization (Cisco Style)
The dashboard was designed to mimic the **Cisco Packet Tracer** interface. It provides:
- **Gridded Topology View:** Nodes are represented as circular icons on a logical grid.
- **Real-Time Packet Tracking:** Users can see individual packets (black squares) moving between nodes.
- **Color-Coded Links:** Links change color based on quality (Green = Stable, Red = Failing).
- **Interactive Control Sidebar:** Change node count, speed, and traffic load without restarting the software.

### 5.2 Physical & Mobility Modeling
The simulator includes:
- **Path Loss Models:** Accurately calculates how signal strength drops over distance.
- **Random Waypoint Mobility:** Nodes pick a random destination and speed, move there, pause, and repeat.
- **Energy Modeling:** Each transmission consumes "battery," and nodes "die" when they reach zero, challenging the protocol to find new paths.

---

## 6. Methodology
Our experiments involved comparing **CPQR** against **AODV** (Reactive) and **OLSR** (Proactive) under three scenarios:
1.  **Static Low-Load:** Testing basic connectivity.
2.  **High-Mobility:** Nodes moving at 15m/s (average driving speed).
3.  **Stress Test:** 50+ nodes with massive traffic bursts.

We measured four Key Performance Indicators (KPIs):
- **PDR (Packet Delivery Ratio):** Percentage of packets that reached the destination.
- **End-to-End Delay:** Average time taken for delivery.
- **Control Overhead:** How much "extra" data was used for routing.
- **Throughput:** Total data handled by the network per second.

---

## 7. Results & Discussion
Our findings showed that:
- **Adaptability:** CPQR significantly outperformed AODV in high-congestion scenarios because it "sensed" traffic jams and routed packets around them.
- **Resilience:** In high-mobility tests, CPQR’s Link Lifetime prediction allowed it to maintain a higher PDR than OLSR, which struggled to keep up with the fast-changing topology.
- **Learning Curve:** Initially, CPQR performed similarly to a shortest-path algorithm (AODV). However, after 30-60 seconds of "learning," its PDR increased as the Q-tables converged on the most reliable paths.

---

## 8. User Guidelines
To use this research tool, follow these steps:

### 8.1 Setup
1. Clone the repository and install Python 3.12+.
2. Install dependencies: `pip install -r requirements.txt`.

### 8.2 Launching the Dashboard
Run the following command:
```bash
python mesh_routing/main.py --live
```
Open your browser to `http://localhost:8050`. Use the sidebar to set your parameters and click **START SIMULATION**.

### 8.3 Running Experiments
To generate data for your own research paper:
- Use the `experiments/run_batch.py` script to run automated tests.
- Use `experiments/plot_results.py` to generate publication-ready charts.

---

## 9. Conclusion
This project demonstrates that Reinforcement Learning is a viable and powerful approach for the next generation of Wireless Mesh Networks. By combining Q-Learning with congestion awareness and link-stability prediction, CPQR creates a "self-healing" network capable of navigating the challenges of a mobile, high-traffic world.

### Future Work
- **Security:** Implementing detection for "Black Hole" attacks where a node claims to be the best path but drops all packets.
- **Multi-Agent Coordination:** Allowing nodes to share their Q-tables with neighbors to speed up learning.

---

## 10. References
1. Boyan, J. A., & Littman, M. L. (1994). *Packet routing in dynamic networks: A reinforcement learning approach.* Advances in Neural Information Processing Systems.
2. Perkins, C. E., & Royer, E. M. (1999). *Ad-hoc on-demand distance vector routing.* WMCSA '99.
3. Clausen, T., & Jacquet, P. (2003). *Optimized Link State Routing Protocol (OLSR).* RFC 3626.
4. Sutton, R. S., & Barto, A. G. (2018). *Reinforcement Learning: An Introduction.* MIT Press.
