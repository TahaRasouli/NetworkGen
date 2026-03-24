# 🐜 Swarm Intelligence: Ant Colony Optimization (ACO) 
**For Automated Renovation Routing**

This module (`ants.py`) implements a custom Ant Colony Optimization algorithm to find the absolute shortest path for renovation workers navigating complex, dynamically generated building floorplans.

---

## 1. The Biological Inspiration
Our routing engine is directly inspired by how blind, simple ants find the shortest path between their nest and a food source. 

When an ant colony looks for food, they initially wander at random. As they walk, they leave behind a chemical trail called a **pheromone**. When an ant finds food, it follows its own trail back home, dropping *more* pheromones. If Ant A takes a short path and Ant B takes a long path, Ant A will finish its round-trip much faster, allowing it to run the path again and drop more pheromones in the same amount of time. Because ants are probabilistically programmed to follow stronger smells, the colony naturally abandons long paths as their pheromones evaporate, eventually marching in a perfect, highly optimized line.

In our system:
* **The Nest:** The building entrance.
* **The Food:** The completion of all dirty rooms.
* **The Path:** The Traveling Salesperson Problem (TSP).

---

## 2. Our Architecture: "Macro vs. Micro" Routing
Standard ACO algorithms fail on building floorplans because of **dead-ends**. If a standard ant walks into a dead-end room, all its immediate neighbors have already been visited. The math divides by zero, and the AI crashes.

To fix this, `ants.py` decouples the *Macro Strategy* from the *Micro Pathing*.

1. **The Smart GPS (Macro):** Before the ants spawn, we use SciPy's `shortest_path(csgraph=dist_matrix_for_pathing, directed=False, return_predecessors=True)` function. This builds an `all_pairs_distances` matrix, allowing ants to "teleport" conceptually and say, *"I am in Room 5, I will go clean Room 42 next,"* knowing the exact physical distance even if walls are in the way.
2. **Unpacking the Tour (Micro):** Once the swarm finds the optimal sequence of rooms (`best_macro_tour`), we pass that sequence into our custom `get_physical_path(start, end, preds)` function. This reads SciPy's `predecessors` matrix to inject the actual, physical hallways the worker must walk to transit between those targets.

---

## 3. The Mathematical Translation (Code Mapping)
Because calculating every possible route through a 50+ room building results in astronomical combinations, brute-forcing it is impossible. The `run_ant_colony` function solves it using a state machine with two distinct phases.

### Phase 1: The Probabilistic Walk (Exploration)
Inside the `for ant in range(n_ants):` loop, the ant stands in a room and looks at its `unvisited` checklist. It calculates the "Attractiveness" of every remaining room using this formula:

$$P_{xy} = \frac{(\tau_{xy}^\alpha) \times (\eta_{xy}^\beta)}{\sum (\tau^\alpha \times \eta^\beta)}$$

* **$\tau$ (Tau - The Pheromone):** The historical success of this hallway. Pulled from our `pher_values = pheromones[current_node, candidates]` array. Scaled by the `alpha` parameter.
* **$\eta$ (Eta - The Heuristic):** The physical distance. Closer rooms are inherently more attractive. Calculated as `heuristic = 1.0 / (dist_values + 1e-10)`. Scaled by the `beta` parameter.

The ant rolls a weighted digital dice using `np.random.choice(candidates, p=probabilities)`. It doesn't *always* pick the closest room—this built-in randomness forces the swarm to explore weird routes that might secretly be shortcuts.

### Phase 2: Evaporation & Deposit (Learning)
Once all ants finish their tours, the colony updates its shared memory.
1. **Evaporation:** `pheromones *= (1.0 - decay)`. Every hallway loses a percentage of its smell (e.g., 10%). Without this, the ants would get permanently stuck on the first "okay" path they found.
2. **Deposit:** The shorter the path, the heavier the pheromone dropped. Calculated as `deposit_amount = 100.0 / length`. This value is added to `pheromones[u, v]`.

---

## 4. A Numerical Walkthrough (Iteration 1)
To see how this math forces intelligence out of randomness, imagine a micro-map with an Entrance (Room 0) and three dirty rooms (1, 2, and 3). We will trace 2 Ants during the very first iteration.

**Parameters:** `alpha = 1.0`, `beta = 2.0`, `decay = 0.1`

#### The Setup (`run_ant_colony` initialization)
* **Smart GPS (`all_pairs_distances`):** Room 1 is 2m away, Room 2 is 4m away, and Room 3 is 5m away.
* **Blank Slate (`pheromones`):** The matrix is initialized with a tiny baseline of `0.1` so the math doesn't multiply by zero.

#### Step 1: The Math (Calculating Probabilities)
Ant 1 and Ant 2 spawn at the Entrance. They run the "Attractiveness" formula `(Pheromone * (1 / Distance^2))` for their unvisited candidates:
* **Path to Room 1:** $0.1 \times (1 / 2^2)$ = **0.02500**
* **Path to Room 2:** $0.1 \times (1 / 4^2)$ = **0.00625**
* **Path to Room 3:** $0.1 \times (1 / 5^2)$ = **0.00400**
* *Sum of Probabilities = 0.03525*

#### Step 2: The Dice Roll (`np.random.choice`)
The ant converts those scores into percentages (`probabilities /= probabilities.sum()`):
* Room 1: **71% chance**
* Room 2: **18% chance**
* Room 3: **11% chance**

*Ant 1* rolls the dice, hits the 71%, and walks to Room 1. 
*Ant 2* rolls the dice, lands in the 18% margin, and wanders off to Room 2. *(This is the swarm exploring!)*

#### Step 3: Fast Forward (Completing `all_tours`)
The ants repeat this until their checklists are empty and return to the start.
* **Ant 1 Tour:** (0 -> 1 -> 2 -> 3 -> 0). `tour_length` = **11 meters**.
* **Ant 2 Tour:** (0 -> 2 -> 3 -> 1 -> 0). `tour_length` = **13 meters**.

#### Step 4: The Matrix Wipe (Evaporation)
Before depositing, the system applies the `decay` rate: `pheromones *= (1.0 - 0.1)`. 
Every unvisited hallway drops from $0.1$ to **$0.09$**. Old paths naturally die off.

#### Step 5: The Secret Sauce (Pheromone Deposit)
The ants evaluate their `tour_length` and drop new pheromones (`deposit_amount = 100.0 / length`).
* **Ant 1 (Winner):** `100 / 11` = drops **+9.09** on its path.
* **Ant 2 (Loser):** `100 / 13` = drops **+7.69** on its path.

#### The Result: Ready for Iteration 2
Notice that **both** ants ended up walking down the hallway between **Room 2 and Room 3**. 
When the next iteration starts, the `pheromones[2, 3]` value isn't $0.09$ anymore. It is $0.09 + 9.09 + 7.69$ = **16.87**. 

Meanwhile, a bad hallway that neither ant took remains at a miserable **0.09**. 

When Iteration 2 begins, that massive $16.87$ multiplier acts like a gravitational pull in the probability formula, dragging almost all 50 ants toward the optimal segments. By Iteration 50, the math compresses so aggressively that 99% of the ants are marching in a single, mathematically verified line.
