# Bridge-Only Repair Routing with Capacity

This document presents the **complete technical solution** for the bridge-repair optimization problem, using a **bridge-only network** in which **depots are bridges and are themselves repairable**. Each team must **start and return to its depot**, and each team has a **total workload capacity** over the planning horizon. The solution is formulated as a **Mixed-Integer Linear Program (MILP)** and is followed by a **Gurobi (Python API) implementation scheme**.

---

## 1. Problem Overview

We consider a post-disaster infrastructure recovery problem in which multiple repair teams are dispatched from designated depot bridges to restore damaged bridges. Each bridge can be repaired at most once, yields a resilience (BFI) improvement if repaired, consumes workload and time, and must be repaired within a given time window. Each team has a limited total workload capacity and must complete a **closed tour** that starts and ends at its depot bridge.

The objective is to **maximize total resilience improvement** subject to routing, timing, workload, and (optionally) cost constraints.

---

## 2. Sets and Indices

- \(V\): set of all bridge nodes
- \(D \subseteq V\): set of depot bridges
- \(K\): set of team types

Team instances are indexed by \((d,k)\) with \(d \in D\), \(k \in K\).

Indices:
- \(i,j \in V\)
- \(d \in D\)
- \(k \in K\)

---

## 3. Parameters

### Travel and Service
- \(\eta_{ij} \ge 0\): travel time from bridge \(i\) to bridge \(j\)
- \(\tau_{ik} \ge 0\): service duration to repair bridge \(i\) by team type \(k\)
  - Typically \(\tau_{ik} = q_i / r_k\), where \(q_i\) is workload and \(r_k\) is team productivity

### Time Windows
- \(a_i\): earliest start time for repairing bridge \(i\)
- \(b_i\): latest completion time for repairing bridge \(i\)

### Resilience (BFI)
- \(\xi_i \in [0,1]\): initial BFI of bridge \(i\)
- \(\delta_k \ge 0\): improvement provided by team type \(k\)
- \(\xi_{ik}^{new} = \min(\xi_i + \delta_k, 1)\)
- \(\Delta\xi_{ik} = \xi_{ik}^{new} - \xi_i\)

### Workload Capacity
- \(q_i \ge 0\): workload proxy for bridge \(i\)
- \(Q_k \ge 0\): total workload capacity for team type \(k\)

### Cost (optional)
- \(c_{ik} \ge 0\): cost of repairing bridge \(i\) by team type \(k\)

### Big-M
- \(M_t\): sufficiently large constant for time precedence and window constraints

---

## 4. Decision Variables

### Routing
- \(x_{ij}^{dk} \in \{0,1\}\): 1 if team \((d,k)\) travels directly from bridge \(i\) to bridge \(j\)

### Repair Assignment
- \(y_i^{dk} \in \{0,1\}\): 1 if team \((d,k)\) repairs bridge \(i\)

### Timing
- \(s_i^{dk} \ge 0\): start time of repairing bridge \(i\) by team \((d,k)\)

### Team Activation
- \(u^{dk} \in \{0,1\}\): 1 if team \((d,k)\) is deployed

### Subtour Elimination (MTZ)
- \(p_i^{dk} \ge 0\): visit order of bridge \(i\) for team \((d,k)\), defined for \(i \in V \setminus \{d\}\)

---

## 5. Objective Functions

### Primary Objective: Maximize Resilience

\[
\max \; Z = \sum_{i \in V} \sum_{d \in D} \sum_{k \in K} \Delta\xi_{ik} \, y_i^{dk}
\]

### Secondary Objective (Optional): Minimize Cost

\[
\min \; W = \sum_{i \in V} \sum_{d \in D} \sum_{k \in K} c_{ik} \, y_i^{dk}
\]

### Pareto Form (\(\varepsilon\)-constraint)

\[
\sum_{i,d,k} c_{ik} \, y_i^{dk} \le \varepsilon, \quad \max Z
\]

---

## 6. Constraints

### (C1) Each Bridge Repaired at Most Once

\[
\sum_{d \in D} \sum_{k \in K} y_i^{dk} \le 1 \quad \forall i \in V
\]

---

### (C2) Closed Tour: Start and Return to Depot

\[
\sum_{j \in V} x_{dj}^{dk} = u^{dk}, \quad \sum_{i \in V} x_{id}^{dk} = u^{dk}
\quad \forall d \in D, k \in K
\]

---

### (C3) Flow–Repair Linking (Non-Depot Nodes)

For each team \((d,k)\) and bridge \(i \ne d\):

\[
\sum_{j \in V} x_{ji}^{dk} = y_i^{dk}, \quad \sum_{j \in V} x_{ij}^{dk} = y_i^{dk}
\]

Depot repair is allowed but bounded:

\[
y_d^{dk} \le u^{dk} \quad \forall d,k
\]

---

### (C4) Team Workload Capacity

\[
\sum_{i \in V} q_i \, y_i^{dk} \le Q_k \, u^{dk}
\quad \forall d \in D, k \in K
\]

---

### (C5) Depot Time Anchor

\[
s_d^{dk} = 0 \quad \forall d,k
\]

---

### (C6) Time Precedence (Service + Travel)

\[
s_j^{dk} \ge s_i^{dk} + \tau_{ik} \, y_i^{dk} + \eta_{ij} - M_t (1 - x_{ij}^{dk})
\quad \forall d,k, \forall i \ne j
\]

---

### (C7) Time Windows (Activated Only if Repaired)

\[
s_i^{dk} \ge a_i - M_t (1 - y_i^{dk})
\quad \forall i,d,k
\]

\[
s_i^{dk} + \tau_{ik} \, y_i^{dk} \le b_i + M_t (1 - y_i^{dk})
\quad \forall i,d,k
\]

---

### (C8) Subtour Elimination (MTZ)

For each team \((d,k)\) and bridges \(i,j \in V \setminus \{d\}\), \(i \ne j\):

\[
p_i^{dk} - p_j^{dk} + |V| \, x_{ij}^{dk} \le |V| - 1
\]

Bind order to repair:

\[
1 \le p_i^{dk} \le |V| \, y_i^{dk}
\quad \forall i \in V \setminus \{d\}
\]

---

## 7. Gurobi Implementation Scheme (Python API)

### Step 1: Data Preparation

- Build sets: `V`, `D`, `K`
- Precompute travel times `eta[i,j]`
- Define parameters: `q[i]`, `Q[k]`, `a[i]`, `b[i]`, `tau[i,k]`, `delta[k]`

### Step 2: Model and Variables

```python
m = gp.Model()

x = m.addVars(D, K, V, V, vtype=GRB.BINARY, name="x")
y = m.addVars(D, K, V, vtype=GRB.BINARY, name="y")
s = m.addVars(D, K, V, vtype=GRB.CONTINUOUS, lb=0, name="s")
u = m.addVars(D, K, vtype=GRB.BINARY, name="u")
p = m.addVars(D, K, V, vtype=GRB.CONTINUOUS, lb=0, name="p")
```

Add `x[d,k,i,i] == 0` constraints.

---

### Step 3: Constraints

Implement constraints (C1)–(C8) using nested loops over indices, guarding cases where `i == d` for flow and MTZ constraints.

---

### Step 4: Objective

```python
m.setObjective(
    gp.quicksum(delta_xi[i,k] * y[d,k,i]
                for d in D for k in K for i in V),
    GRB.MAXIMIZE
)
```

Add cost budget constraint if using the \(\varepsilon\)-constraint approach.

---

### Step 5: Optimization and Extraction

```python
m.optimize()
```

Extract:
- repaired bridges: `y[d,k,i] == 1`
- routes: `x[d,k,i,j] == 1`
- schedules: `s[d,k,i]`

Validate:
- closed tours
- no subtours
- time-window feasibility
- workload capacity satisfaction

---

## 8. Remarks

- The model is a **multi-depot, capacitated, time-windowed repair routing problem**.
- Using only bridge nodes simplifies notation and implementation while preserving realism.
- For large instances, replace MTZ with flow-based subtour elimination or lazy cuts.
- The formulation is directly compatible with Gurobi’s MILP solver and supports Pareto analysis via \(\varepsilon\)-constraints.

---

**End of Technical Solution**

