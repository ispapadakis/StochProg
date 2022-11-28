"""Stochastic Programming Example
Bioreactor Scheduling 2 Periods Under 3 Scenarios
"""
from ortools.linear_solver import pywraplp
import yaml
import numpy as np
import pandas as pd
import sys
import os
import datetime

def get_avg_demand(demand):
    prob = np.array([s['prob'] for s in demand])
    v = np.array([s['vector'] for s in demand])
    return v.T.dot(prob)

def assess_status(status, mod):
    if status == pywraplp.Solver.OPTIMAL:
        out = "\nOptimal Solution Found\n\n"
        out += 'Problem solved in %.0f milliseconds\n' % mod.wall_time()
        out += 'Problem solved in %d iterations\n' % mod.iterations()
        out += 'Problem solved in %d branch-and-bound nodes\n' % mod.nodes()
        return out
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
    print('Decision Variables: ({:^5}):'.format(mod.NumVariables()), file=file)
    print('---------------------------', file=file)
    varname = []
    optvalue = [] 
    for v in mod.variables():
        varname.append(v.name())
        optvalue.append(v.solution_value())
        if v.integer():
            if v.solution_value() > 0.5:
                print(v.name(), file=file)
        else:
            ln = v.name()+"-"*50
            if np.abs(v.solution_value()) > 1e-4:
                print("{}:{:10.3f}".format(ln[:60], v.solution_value()), file=file)
    optx = np.array(optvalue)
    print('\n\nModel Constraints ({:^5}):'.format(mod.NumConstraints()), file=file)
    print("{:50} {:>10} {:>10} {:>10}".format('--------------------------',"LB","Value","UB"), file=file)
    for cons in mod.constraints():
        coef = np.array([cons.GetCoefficient(v) for v in mod.variables()])
        print("{:50} {:10.3f} {:10.3f} {:10.3f}".format(cons.name(), cons.lb(), coef.dot(optx), cons.ub()), file=file)
    return obj, pd.Series(optvalue, index=varname, name='OptimalValues')

def main():
    
    model_path = os.path.dirname(__file__)
    
    with open(os.path.join(model_path,"model_data_2stg.yml"))as f:
        data = yaml.load(f, Loader=yaml.FullLoader)
        
    scenarios = [s['name'] for s in data["Demand_Scenarios"]]
    brand_idx = {brand:i for i, brand in enumerate(data["Brands"])}
        
    ### Declare Model
    solver = pywraplp.Solver.CreateSolver('SCIP')
    if not solver:
        sys.exit('Solver Unavailable')
    
    ### Declare Variables
    
    # Production Period 1
    
    xp1 = {
        (reactor,brand): solver.BoolVar('produce {:2} at {:3} on P1'.format(brand, reactor))
        for reactor in data['Bioreactors']
        for brand in data['Prod_Data']['Std'][reactor]
    }
    
    # Production Period 2
    
    xp2 = {
        (reactor,brand,ptype,scenario): solver.BoolVar('produce {:2} at {:3} using {:3} on P2 if {}'.format(
            brand, reactor, ptype, scenario))
        for scenario in scenarios
        for ptype in data["Prod_Data"]
        for reactor in data["Prod_Data"][ptype]
        for brand in data['Prod_Data'][ptype][reactor]
    }
   
    # Stock Out Quantity
    
    so = {
        (period, scenario, brand): solver.NumVar(0, solver.infinity(), 'stockout  of {:2} on {:2} if {}'.format(brand,period,scenario))
        for period in data['Periods']
        for scenario in scenarios
        for brand in data['Brands']
    }
    
    # New Inventory
    
    ni = {
        (period, scenario, brand): solver.NumVar(0, solver.infinity(), 'inventory of {:2} on {} if {:2}'.format(brand,period,scenario))
        for period in data['Periods']
        for scenario in scenarios
        for brand in data['Brands']
    }
    
    # Ending Inventory Test
    
    ei = {
        scenario:solver.BoolVar('end inventory True if {}'.format(scenario))
        for scenario in scenarios
    }
    
    
    ### Declare Constraints
    
    # Material Flow Constraints
    # Production + Stockouts + PriorInventory == Demand + NewInventory OR
    # Production + Stockouts - NewInventory == Demand - PriorInventory OR

    # End of Period 1
    
    for i, brand in enumerate(data['Brands']):
        for d in data["Demand_Scenarios"]:
            scenario = d['name']
            bdemand = d['vector'][i]
            prod_q = [ 
            xp1[reactor,brand]*data["Prod_Data"]["Std"][reactor][brand]["Capacity"]
            for reactor in data['Bioreactors'] 
            if brand in data["Prod_Data"]["Std"][reactor]
            ]
            solver.Add(
                sum(prod_q) + so["P1",scenario,brand] - ni["P1",scenario,brand] == bdemand - data['Prior_Inventory'][brand], 
                "p1_mflow_{} if {}".format(brand, scenario)
                )
    
    # End of Period 2
    
    for i, brand in enumerate(data['Brands']):
        for d in data["Demand_Scenarios"]:
            scenario = d['name']
            bdemand = d['vector'][i]
            prod_q = [ 
            xp2[reactor,brand,ptype,scenario]*data["Prod_Data"][ptype][reactor][brand]["Capacity"]
            for ptype in data["Prod_Data"]
            for reactor in data["Prod_Data"][ptype]
            if brand in data["Prod_Data"][ptype][reactor]
            ]
            solver.Add(
                sum(prod_q) + so["P2",scenario,brand] - ni["P2",scenario,brand] + ni["P1",scenario,brand] == bdemand, 
                "p2_mflow_{} if {}".format(brand, scenario)
                )
    
    # Capacity Constraints
    
    # Period 1
    
    for reactor in data['Bioreactors']:
        utilization = [
            xp1[reactor,brand] 
            for brand in data['Brands']
            if (reactor,brand) in xp1
        ]
        solver.Add( sum(utilization) == 1, "p1_capacity_{}".format(reactor))
    
    # Period 2
    
    for reactor in data['Bioreactors']:
        for scenario in scenarios:
            utilization = [
                xp2[reactor,brand,ptype,scenario]
                for r,brand,ptype,s in xp2
                if r == reactor and s == scenario
            ]
            solver.Add( sum(utilization) == 1, "p2_capacity_{} if {}".format(reactor, scenario))

        
    # Remaining Constraints
    
    # Period 1
        
    for cname, (v, _, lim) in [(constr, data[constr]) for constr in ['Downstream_Constr', 'Delivery_Constr']]:
        utilization = [
            v[i]*xp1[reactor,brand]*data["Prod_Data"]["Std"][reactor][brand]["Capacity"]
            for reactor in data['Bioreactors']
            for i, brand in enumerate(data['Brands'])
            if (reactor,brand) in xp1
        ]
        solver.Add(
            sum(utilization) <= lim, 
            "P1 {}".format(cname)
            )
    
    # Period 2
    
    for scenario in scenarios:
        for cname, (v, _, lim) in [(constr, data[constr]) for constr in ['Downstream_Constr', 'Delivery_Constr']]:
            utilization = [
                v[brand_idx[brand]]*xp2[reactor,brand,ptype,scenario]*data["Prod_Data"][ptype][reactor][brand]["Capacity"]
                for ptype in data["Prod_Data"]
                for reactor in data["Prod_Data"][ptype]
                for brand in data["Prod_Data"][ptype][reactor]
            ]
            solver.Add(
                sum(utilization) <= lim, 
                "P2 {} if {}".format(cname, scenario)
                )
             
    # Bleed Feed Available Only in P2 only if Brand is Produced in P1
    
    for reactor in data["Prod_Data"]["BF"]:
        for brand in data["Prod_Data"]["BF"][reactor]:
            for scenario in scenarios:
                solver.Add(
                    xp2[reactor,brand,"BF",scenario] <= xp1[reactor,brand], 
                    "bf_available for {} at {} if {}".format(brand, reactor, scenario)
                    )
       
    # End Inventory Constraints
    #   May Apply to All Scenarios
    #   or Apply in probability, say greater than 75%
    
    for scenario in scenarios:
        for brand in data["Brands"]:
            solver.Add(
                ni["P2",scenario,brand] >= data["End_Inventory"][brand] * ei[scenario], 
                "end_inventory_{} if {}".format(brand, scenario)
                )
            
    # Exceed Prob Limit
    solver.Add(
                sum(s['prob']*ei[s['name']] for s in data["Demand_Scenarios"]) >= data['End_Inventory']['ProbLimit'], 
                "end_inventory_true_in_probability"
                )
    
    # Declare Objective: Maximize Profit
    
    profit = solver.Objective()
    
    # Prod Quantity Multipliers Period 1
    for reactor in data["Prod_Data"]["Std"]:
        for brand in data["Prod_Data"]["Std"][reactor]:
            d = data["Prod_Data"]["Std"][reactor][brand]
            profit_mult = data['Revenue'][brand_idx[brand]]-d['ProdCost']
            profit.SetCoefficient(xp1[reactor,brand], profit_mult*d['Capacity'])
    
    # Prod Quantity Multipliers Period 2
    for ptype in data["Prod_Data"]:
        for reactor in data["Prod_Data"][ptype]:
            for brand in data["Prod_Data"][ptype][reactor]:
                i = brand_idx[brand]
                d = data["Prod_Data"][ptype][reactor][brand]
                profit_mult = data['Revenue'][i]-d['ProdCost']
                for s in data["Demand_Scenarios"]:
                    profit.SetCoefficient(
                        xp2[reactor,brand,ptype,s['name']], 
                        profit_mult*d['Capacity']*s['prob']
                        )
                
    # Stockout Quantity Multipliers
    for period in data['Periods']:
        for i, brand in enumerate(data['Brands']):
            for s in data["Demand_Scenarios"]:
                profit.SetCoefficient(so[period, s['name'], brand], -data['Stockout_Cost'][i] * s['prob'])
        
    # New Inventory Quantity Multipliers
    for period in data['Periods']:
        for i, brand in enumerate(data['Brands']):
            for s in data["Demand_Scenarios"]:
                profit.SetCoefficient(ni[period, s['name'], brand], -data['Inventory_Cost'][i] * s['prob'])
                    
    profit.SetMaximization()
    
    model_summary(solver).to_csv(os.path.join(model_path,"model_summary.csv"))
    
    # Run Model and Write Results to File
    
    with open(os.path.join(model_path,"optimal_result.txt"), "w") as f:
        print("Model Run On", datetime.datetime.today().isoformat(), file=f)
        # SOLVE MODEL
        status = solver.Solve()
        print(assess_status(status, solver), file=f)
        _, optsettings = print_model_results(solver, f)
        optsettings.to_frame().transpose().to_csv(os.path.join(model_path,"optimal_values.csv"))

if __name__ == "__main__":
    main()


