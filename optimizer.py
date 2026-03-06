from pulp import *

def optimize_production(freq, price, target, Pmax):

    hours = len(freq)

    # -------- Feature Engineering --------
    
    # frequency surplus
    freq_surplus = [f - 50 for f in freq]
    w1=-1
    w2=1
    startup_cost=120
    # normalization function
    def normalize(arr):
        mn = min(arr)
        mx = max(arr)
        if mx == mn:
            return [0]*len(arr)
        return [(x - mn) / (mx - mn) for x in arr]

    freq_norm = normalize(freq_surplus)
    price_norm = normalize(price)

    # final score
    score = [w1*freq_norm[h] + w2*price_norm[h] for h in range(hours)]

    # -------- Optimization Model --------
    
    model = LpProblem("Electrolyser_Optimization", LpMinimize)

    P = LpVariable.dicts("Production", range(hours), 0, Pmax)
    x = LpVariable.dicts("ON", range(hours), 0, 1, LpBinary)
    s = LpVariable.dicts("Start", range(hours), 0, 1, LpBinary)

    # objective
    model += lpSum(score[h]*P[h] + startup_cost*s[h] for h in range(hours))

    # daily production target
    model += lpSum(P[h] for h in range(hours)) == target

    # production only when ON
    for h in range(hours):
        model += P[h] <= Pmax * x[h]

    # startup detection
    model += s[0] >= x[0]
    for h in range(1, hours):
        model += s[h] >= x[h] - x[h-1]

    model.solve(PULP_CBC_CMD(msg=0))

    production = [value(P[h]) for h in range(hours)]

    return production
