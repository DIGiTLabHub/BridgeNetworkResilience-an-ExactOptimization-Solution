# MD-VRPDW Design (Bridge Nodes, Multi-Depot, Time Windows)

## 1. Scope and Updates
This design replaces the prior city–bridge layered network with a single-layer graph where **bridges are the nodes**. A subset of bridge nodes are selected as depots (1–3). The model is a **multi-depot vehicle routing problem with time windows** and **bi-objective optimization** (maximize resilience, minimize cost) using an **ε-constraint** method. The solution is an **exact MILP solved by Gurobi (branch-and-bound/branch-and-cut), not heuristic**.

## 2. Sets and Indices
- `B`: set of bridges (all nodes in the routing graph)
- `D ⊆ B`: selected depots (bridge nodes used as depots)
- `N = B` if depot bridges are repairable; `N = B \ {MoDOT}` when MoDOT is selected
- `K`: team types (RRU, ERT, CIRS)
- `A ⊆ B × B`: directed arcs between bridge nodes
- `T`: planning horizon (continuous time or discretized, see assumptions)

## 3. Parameters
- `τ_ij`: travel time between bridges `i` and `j` (from shortest-path distance)
- `θ_k`: service duration for team type `k`
- `a_i, b_i`: time window for bridge `i` (earliest start, latest finish)
- `ξ_i`: initial bridge functionality index (BFI)
- `δ_k`: restoration improvement for team type `k`
- `ξ_ik^new = min(ξ_i + δ_k, 1)`
- `c_ik`: restoration cost for team `k` on bridge `i`
- `M`: sufficiently large constant for time constraints
- `ε`: cost bound (used in ε-constraint method)

Optional (if depot selection is part of optimization):
- `F_d`: depot opening cost (set to 0 if not used)

## 4. Decision Variables
Routing and assignment:
- `x_ij^{dk} ∈ {0,1}`: team `k` from depot `d` travels from bridge `i` to `j`
- `y_i^{dk} ∈ {0,1}`: bridge `i` is restored by team `k` from depot `d`
- `s_i^{dk} ≥ 0`: service start time at bridge `i` for team `k` from depot `d`
- `u_{dk} ∈ {0,1}`: team `k` at depot `d` is used (allows idle teams)

Optional (if depot selection is optimized):
- `z_d ∈ {0,1}`: depot `d` is opened

## 5. Objectives (Bi-Objective)
### 5.1 Maximize Resilience
Average post-restoration resilience over all bridges:

`max Z = (1/|B|) [ Σ_{i∈B} Σ_{d∈D} Σ_{k∈K} ξ_ik^new · y_i^{dk} + Σ_{i∈B} ξ_i · (1 - Σ_{d∈D} Σ_{k∈K} y_i^{dk}) ]`

### 5.2 Minimize Cost
Total restoration cost:

`min W = Σ_{i∈B} Σ_{d∈D} Σ_{k∈K} c_ik · y_i^{dk}`

### 5.3 ε-Constraint Method
Solve the bi-objective problem by maximizing `Z` subject to:

`Σ_{i∈B} Σ_{d∈D} Σ_{k∈K} c_ik · y_i^{dk} ≤ ε`

Sweep `ε` across a range to build a Pareto frontier.

## 6. Constraints
### 6.1 Single Restoration
`Σ_{d∈D} Σ_{k∈K} y_i^{dk} ≤ 1  ∀ i ∈ N`

### 6.2 Route–Service Linking
`Σ_{j∈B\{i}} x_ij^{dk} = y_i^{dk}  ∀ i ∈ N, ∀ d,k`

`Σ_{j∈B\{i}} x_ji^{dk} = y_i^{dk}  ∀ i ∈ N, ∀ d,k`

### 6.3 Depot Departure/Return and Team Limits
Each depot has one team per type. Teams may be idle via `u_{dk}`:

`Σ_{j∈B} x_dj^{dk} = u_{dk}  ∀ d∈D, k∈K`

`Σ_{i∈B} x_id^{dk} = u_{dk}  ∀ d∈D, k∈K`

If depot selection is optimized, also require `u_{dk} ≤ z_d`.

### 6.4 Time Propagation
For all arcs `(i,j)`:

`s_j^{dk} ≥ s_i^{dk} + θ_k + τ_ij - M(1 - x_ij^{dk})  ∀ i≠j, ∀ d,k`

### 6.5 Time Windows
`a_i ≤ s_i^{dk}  ∀ i ∈ N, ∀ d,k`

`s_i^{dk} + θ_k ≤ b_i  ∀ i ∈ N, ∀ d,k`

### 6.6 Capacity/Workload (New)
Let `q_i` be the workload proxy at bridge `i` derived from severity (e.g., estimated crew-hours), and `Q_k` the maximum workload per team `k` over the horizon:

`Σ_{i∈N} q_i · y_i^{dk} ≤ Q_k  ∀ d∈D, k∈K`

### 6.7 Variable Domains
`x_ij^{dk} ∈ {0,1}`, `y_i^{dk} ∈ {0,1}`, `s_i^{dk} ≥ 0`

## 7. Depot Selection Rules (Preprocessing)
To align with the updated data pipeline, depots are selected in preprocessing and passed to the optimizer as `D`:
- If number of bridges `≤ 5`: select 1 depot
- If `6–15`: select 2 depots
- If `16–30`: select 3 depots
- If `> 30`: do not proceed (exceeds model capacity)

Depot selection heuristic:
- Include MoDOT if present in the county set
- Otherwise choose central bridge; for 2–3 depots, choose additional farthest bridges to spread coverage

## 8. Notation Mapping (Old → New)
- Old `C` (cities) removed; bridges are now primary nodes
- Old bridges `B` still exist but now `B` is the node set
- Old depots `D ⊂ C` replaced by `D ⊂ B`
- Old assignment `y_it^{dk}` becomes `y_i^{dk}` with continuous time `s_i^{dk}`

## 9. Assumptions and Open Questions
- Depot bridges are repairable except MoDOT (if MoDOT is selected, exclude it from `N`)
- Depot bridges may be repaired by any team
- Travel times `τ_ij` are derived from highway distances between bridges
- Service time `θ_k` is constant per team type
- Time is continuous; discretized `t` can be reintroduced if needed
- Capacity/workload constraints are not in `main.tex`; the model adds a per-team workload bound using a severity-based duration proxy

Open questions for confirmation:
- Workload cap `Q_k` is total-horizon (team-hours over the full planning horizon).

## 10. Implementation Plan (Draft)
1. Lock inputs: depot selection, team types, workload proxy `q_i`, horizon `T`.
2. Define data schema: bridge attributes, time windows, costs, depot set `D`, workload proxy `q_i` from severity.
3. Implement model builder module (sets, variables, objectives, constraints), including `u_{dk}` usage and capacity constraints.
4. Implement ε-constraint loop (Pareto frontier) and capture objective values.
5. Add post-processing (routes, schedules, resilience metrics, depot utilization).
6. Validate against baseline scenario from `main.tex` (small case) and record solve stats.
