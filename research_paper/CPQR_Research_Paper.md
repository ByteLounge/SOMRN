# Self-Optimizing Wireless Mesh Networks: A Congestion-Predictive Reinforcement Learning Approach

**Author:** Yash Sanikop  
**Organization:** ByteLounge Research / Open Source Simulation Initiative  
**GitHub:** [https://github.com/ByteLounge/SOMRN](https://github.com/ByteLounge/SOMRN)  
**Date:** April 19, 2026

---

## I. ABSTRACT
Wireless Mesh Networks (WMNs) are increasingly utilized in dynamic environments, ranging from smart-city deployments to battlefield communication. However, traditional routing protocols such as AODV and OLSR exhibit performance degradation under high mobility and non-uniform traffic loads. This paper proposes a self-optimizing framework centered around a novel Reinforcement Learning (RL) protocol: **Congestion-Predictive Q-Routing (CPQR)**. We present a custom-built, high-fidelity simulator and a Cisco-inspired visualization dashboard. Experimental results indicate that CPQR achieves a robust balance between packet delivery ratio (PDR) and latency by utilizing Predicted Link Lifetime (LLT) and queue-aware reward functions.

---

## II. INTRODUCTION
The fundamental challenge in Wireless Mesh Networks is the frequent change in topology. Unlike traditional Wi-Fi, where a client talks to a fixed Access Point, WMN nodes act as both hosts and routers. 

**Motivation:** Static routing tables are insufficient for networks where routers move at speeds of 5–20 m/s. Reactive protocols suffer from high route-discovery latency, while proactive protocols consume excessive bandwidth. Our research focuses on "Intelligence at the Edge"—enabling every router to learn the best path through trial and error, effectively becoming a self-healing system.

---

## III. DEFINITION OF TERMINOLOGIES
To ensure this paper is accessible to both engineers and researchers, we define the core concepts used in this study:

1.  **WMN (Wireless Mesh Network):** A decentralized network where nodes connect directly, dynamically, and non-hierarchically to as many other nodes as possible.
2.  **PDR (Packet Delivery Ratio):** The ratio of packets successfully received by the destination to the total packets sent by the source. *Formula: (Packets Received / Packets Sent) * 100*.
3.  **Latency (End-to-End Delay):** The time it takes for a data packet to travel from the source node to the destination across the mesh.
4.  **RSSI (Received Signal Strength Indicator):** A measurement of the power present in a received radio signal. Low RSSI indicates a link is about to break.
5.  **EWMA (Exponential Weighted Moving Average):** A statistical technique used to predict future values (like queue depth) by giving more weight to recent data while still considering historical trends.
6.  **Q-Table:** The "brain" of the RL agent. It is a data structure that stores the "quality" (Q-value) of taking a specific action (forwarding to a neighbor) given a state (destination).
7.  **Bellman Equation:** The mathematical foundation of Q-learning, used to update Q-values based on the reward received and the estimated future rewards.
8.  **Next-Hop:** The next immediate node in the path towards the final destination.
9.  **Throughput:** The actual rate at which data is successfully transferred over the network, measured in bits per second (bps) or kbps.
10. **Link Lifetime (LLT):** A prediction of how many seconds a wireless link will remain active before the nodes move out of range.

---

## IV. PROBLEM STATEMENT
Standard routing protocols (RFC 3561, RFC 3626) fail to account for two critical real-world variables:
- **Node Exhaustion:** Traditional protocols may route all traffic through a "central" node until its battery dies, causing a sudden network partition.
- **Congestion Blindness:** A node might have a perfect signal (High RSSI) but a full buffer. Sending more data to this node causes "Queue Overflow," leading to packet loss.

---

## V. PROPOSED ARCHITECTURE: CPQR
The **Congestion-Predictive Q-Routing (CPQR)** protocol treats routing as a multi-objective optimization problem.

### 5.1 The Learning Mechanism
CPQR uses **Distributed Q-Learning**. Every time a packet is delivered, a feedback signal is sent back (implicit acknowledgment). If a packet is dropped, the node that dropped it penalizes that specific route in its local memory.

### 5.2 Mathematical Model
The update rule for a node $u$ sending to destination $d$ via neighbor $v$ is:
$$Q(u, d, v) \leftarrow (1 - \alpha) Q(u, d, v) + \alpha \left[ R + \gamma \min_{v'} Q(v, d, v') \right]$$
Where:
- $\alpha$ (Learning Rate): How much new information overrides old information. (Default: 0.1)
- $\gamma$ (Discount Factor): The importance of future rewards. (Default: 0.9)
- $R$ (Reward): The cost function.

### 5.3 The Reward Function ($R$)
CPQR’s novelty lies in its "Health-Aware" reward:
$$R = \text{Delay} + \beta \times \left( \frac{\text{Queue}_{EWMA}}{\text{Capacity}_{Max}} \right) + W_e \times \text{Energy}_{\text{consumed}}$$
This ensures the protocol avoids nodes that are slow, crowded, or low on battery.

---

## VI. SYSTEM IMPLEMENTATION
The project is divided into four modular layers:

1.  **Physical Layer:** Simulates radio propagation, path loss (using the Log-Distance model), and node positioning.
2.  **Network Layer:** Implements the routing logic (AODV, OLSR, CPQR).
3.  **Simulation Engine:** A discrete-time execution loop that manages mobility steps and packet forwarding.
4.  **Visualization Layer:** A Cisco Packet Tracer-style dashboard built on Dash/Plotly, providing a gridded "Logical View" of the network.

---

## VII. EXPERIMENTAL EVALUATION & STATISTICS
We conducted 500+ simulation runs to compare CPQR against AODV.

### 7.1 Simulation Parameters
| Parameter | Value |
|-----------|-------|
| Area Size | 500m x 500m |
| Tx Range  | 100m |
| Nodes     | 30 - 100 |
| Mobility  | 0 - 30 m/s |
| Duration  | 300s |

### 7.2 Comparative Statistics
Under high-mobility conditions (15 m/s):

| Metric | AODV (Reactive) | CPQR (Proposed) | Improvement |
|--------|-----------------|-----------------|-------------|
| **PDR (%)** | 55.9% | 61.2% | +5.3% |
| **Avg Delay** | 0.82s | 0.46s | -43.9% |
| **Overhead** | Low | Moderate | - |
| **Stability** | Fluctuating | Converging | High |

**Analysis:** CPQR initially has a lower PDR as it explores the network. However, after the "Learning Phase" (approx. 45 seconds), it identifies stable "highways" in the mesh, outperforming AODV which must restart discovery every time a node moves.

---

## VIII. USER GUIDELINES
The simulator is designed for researchers to perform "What-If" analysis.

1.  **Launch Dashboard:** Execute `python main.py --live`.
2.  **Select Nodes:** Use the slider to increase density (more nodes = more possible paths, but higher interference).
3.  **Inject Load:** Increase the packet rate to see when CPQR starts routing *around* congested nodes.
4.  **Export:** Click "Export CSV" to get a timestamped log of all snapshots for use in tools like MATLAB or Excel.

---

## IX. CONCLUSION & FUTURE WORK
The CPQR protocol successfully demonstrates that Reinforcement Learning can significantly reduce latency in Wireless Mesh Networks by predicting congestion and link breaks before they occur. The Cisco-style dashboard provides an intuitive way for engineers to visualize these AI-driven routing decisions.

**Future Directions:**
- **Deep Q-Networks (DQN):** Replacing linear Q-tables with neural networks to handle thousands of nodes.
- **5G/6G Integration:** Adapting the simulator for mmWave high-frequency link characteristics.

---

## X. REFERENCES
1. Boyan, J. A., & Littman, M. L. (1994). *Packet routing in dynamic networks: A reinforcement learning approach.* Advances in Neural Information Processing Systems.
2. Perkins, C. E., & Royer, E. M. (1999). *Ad-hoc on-demand distance vector routing.* IEEE.
3. Clausen, T., & Jacquet, P. (2003). *Optimized Link State Routing Protocol (OLSR).* IETF RFC 3626.
4. Sutton, R. S., & Barto, A. G. (2018). *Reinforcement Learning: An Introduction.* MIT Press.
5. Yash Sanikop. (2026). *SOMRN: Self-Optimizing Mesh Routing Network.* [GitHub Repository].
