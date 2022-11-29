"""Mixed Integer Programming Example
Bioreactor Scheduling 1 Period
"""

from ortools.linear_solver import pywraplp
import yaml
import numpy as np
import pandas as pd
import sys
import os
import datetime

def get_avg_demand(demand):
    prob = np.array([p for _, p,_ in demand])
    v = np.array([x for _, _, x in demand])
    return v.T.dot(prob)

def assess_status(status):
    if status == pywraplp.Solver.OPTIMAL:
        return "\nOptimal Solution Found"
    else:
        if status == pywraplp.Solver.FEASIBLE:
            return "\nStopped At Suboptimal Feasible Solution"
        else:
            sys.exit('The solver could not solve the problem.')
        
def model_summary(mod):
    mod_data = [[cnstr.GetCoefficient(v) for v in mod.variables()] + [cnstr.Lb(), cnstr.Ub()]
                for cnstr in mod.constraints()]
    bnd = ['MIN', None] if mod.Objective().minimization() else [None, 'MAX']
    mod_data += [[mod.Objective().GetCoefficient(v) for v in mod.variables()] + bnd]
    df = pd.DataFrame(
        data = mod_data,
        index =  [cnstr.name() for cnstr in mod.constraints()] + ['Objective'],
        columns = [v.name() for v in mod.variables()] + ['L_Bound','U_Bound']
    )
    return df

def print_model_results(mod, file=sys.stdout):
    obj = mod.Objective().Value()
    print("\nProfit = {:.3f}\n".format(obj), file=file)
    print('Decision Variables:', file=file)
    print('-------------------', file=file)
    varname = []
    optvalue = [] 
    for v in mod.variables():
        varname.append(v.name())
        optvalue.append(v.solution_value())
        print("{:20} {:10.3f}".format(v.name(), v.solution_value()), file=file)
    return obj, pd.Series(optvalue, index=varname, name='OptimalValues')

def main():
    
    model_path = os.path.dirname(__file__)
    
    with open(os.path.join(model_path,"model_data.yml"))as f:
        data = yaml.load(f, Loader=yaml.FullLoader)
        
    ### Declare Model
    solver = pywraplp.Solver.CreateSolver('SCIP')
    if not solver:
        sys.exit('Solver Unavailable')
    
    ### Declare Variables
    
    # Production
    
    x = {
        (reactor,brand): solver.BoolVar('prod_of_{}_at_{}'.format(brand, reactor))
        for reactor in data['Bioreactors']
        for i, brand in enumerate(data['Brands'])
        if data['Capacity_Constr'][reactor][0][i] is not None
    }
    
   
    # Stock Out Quantity
    
    s = {
        brand: solver.NumVar(0, solver.infinity(), 'stockout_of_{}'.format(brand))
        for brand in data['Brands']
    }
    
    # New Inventory
    
    ni = {
        brand: solver.NumVar(0, solver.infinity(), 'inventory_of_{}'.format(brand))
        for brand in data['Brands']
    }
    
    
    ### Declare Constraints
    
    # Material Flow Constraints
    # Product + Prior_Inventory + Stockout = Demand + New_Inventory
    
    avg_demand = get_avg_demand(data['Demand_Scenarios'])
    
    for i, brand in enumerate(data['Brands']):
        demand_q = [ 
           x[reactor,brand]*data["Batch_Size"][reactor][brand] 
           for reactor in data['Bioreactors'] if (reactor,brand) in x
        ]
        demand_q.append(s[brand])
        demand_q.append(-ni[brand])
        solver.Add( sum(demand_q) == avg_demand[i] - data['Prior_Inventory'][brand], "stockout_{}".format(brand))
        
    # Capacity Constraints
    
    for reactor, (v, _, lim) in data['Capacity_Constr'].items():
        utilization = [
            v[i]*x[reactor,brand] 
            for i, brand in enumerate(data['Brands'])
            if (reactor,brand) in x
        ]
        solver.Add( sum(utilization) == lim, "capacity_{}".format(reactor))
        
    # Remaining Constraints
        
    for cname, (v, _, lim) in [(constr, data[constr]) for constr in ['Downstream_Constr', 'Delivery_Constr']]:
        utilization = [
            v[i]*x[reactor,brand]*data["Batch_Size"][reactor][brand]
            for reactor in data['Bioreactors']
            for i, brand in enumerate(data['Brands'])
            if (reactor,brand) in x
        ]
        solver.Add( sum(utilization) <= lim, cname)

    # Declare Objective: Maximize Profit
    
    profit = solver.Objective()
    
    # Prod Quantity Multipliers
    for i, brand in enumerate(data['Brands']):
        for reactor in data['Bioreactors']:
            if (reactor,brand) in x:
                profit_mult = data['Revenue'][i]-data['Production_Cost'][i]
                profit.SetCoefficient(x[reactor,brand], profit_mult*data['Batch_Size'][reactor][brand])
                
    # Stockout Quantity Multipliers
    for i, brand in enumerate(data['Brands']):
        profit.SetCoefficient(s[brand], -data['Stockout_Cost'][i])
        
    # New Inventory Quantity Multipliers
    for i, brand in enumerate(data['Brands']):
        profit.SetCoefficient(ni[brand], -data['Inventory_Cost'][i])
                    
    profit.SetMaximization()
    
    model_summary(solver).to_csv(os.path.join(model_path,"model_summary.csv"))
    
    # Run Model and Write Results to File
    
    with open(os.path.join(model_path,"optimal_result.txt"), "w") as f:
        print("Model Run On", datetime.datetime.today().isoformat(), file=f)
        # SOLVE MODEL
        status = solver.Solve()
        print(assess_status(status), file=f)
        _, optsettings = print_model_results(solver, f)
        optsettings.to_frame().transpose().to_csv(os.path.join(model_path,"optimal_values.csv"))

if __name__ == "__main__":
    main()


