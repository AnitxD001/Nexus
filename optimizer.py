import pulp

def optimize_production(grid, renew, target, Pmax, startup_cost):

    hours = 24
    min_load = 0.1 * Pmax   # electrolyser minimum load
    price=[]
    # electricity price used
    g=0

    price = [min(grid[h], renew[h]) for h in range(hours)]

    prob = pulp.LpProblem("Electrolyser_Scheduling", pulp.LpMinimize)

    # Variables
    x = pulp.LpVariable.dicts("ON", range(hours), cat="Binary")
    P = pulp.LpVariable.dicts("Production", range(hours), lowBound=0)
    s = pulp.LpVariable.dicts("Startup", range(hours), cat="Binary")

    # Objective
    prob += pulp.lpSum(price[h] * P[h]*50 for h in range(hours)) \
            + startup_cost * pulp.lpSum(s[h] for h in range(hours))

    # Hydrogen production target
    prob += pulp.lpSum(P[h] for h in range(hours)) == target

    for h in range(hours):

        # production limits
        prob += P[h] <= Pmax * x[h]
        prob += P[h] >= min_load * x[h]

        # startup detection
        if h == 0:
            prob += s[h] >= x[h]
        else:
            prob += s[h] >= x[h] - x[h-1]
            prob += s[h] <= x[h]
            prob += s[h] <= 1 - x[h-1]

    # Solve
    prob.solve(pulp.PULP_CBC_CMD(msg=0))

    production = [P[h].varValue for h in range(hours)]
    tot=0
    for i in range(len(production)):
        if production[i]>0:
            if(grid[i]==price[i]):
                g+=1
            tot+=1
    g=(g/tot)*100
    s=sum(production[h]*50*price[h] for h in range(hours))
    return production, g, s
renew = [
3.2,5,3.0,2.9,2.8,2.6,
2.3,2.1,2.0,1.9,1.8,1.7,
3.1,6,5,4.4,4.5,2.9,
3.3,3.6,float('inf'),float('inf'),float('inf'),float('inf')
]

grid = [
3.2,4,2.8,2.7,2.9,4.2,
4.2,5.0,5.5,5.8,5.6,5.2,
4.8,7,4.3,2,3,6.0,
6.5,6.2,5.6,3,2,2.5
]

print(optimize_production(grid, renew, target=1060, Pmax=60, startup_cost = 15000))