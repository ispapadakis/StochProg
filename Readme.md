# Bioreactor Optimization Examples

## [Basic Optimization Modeling](BioReactorSingleBatch/build_model.py)
<img src="./docs/OnePeriodModel.png" alt="pictorial" width="500"/><br>
- 3 Products [A, C, R<sub>+</sub>]
- 2 Bioreactors [ BR1, BR2 ]

#### Schedule Production for 1 Period
<u>Maximize</u> Net Revenue

(Revenue net of Production Cost, Stockout Cost, and Inventory Cost)

While the following constraints are satisfied:

- *Capacity Constraint*: Only 1 Product Per Bioreactor
- *Downstream Constraint*: Downstream Technical Requirement
- *Delivery Constraint*: Delivery Technical Requirement
- *Material Flow Constraint*: Product + Prior_Inventory + Stockout = Demand + New_Inventory

See Full Model Data in [Data Dictionary](BioReactorSingleBatch/model_data.yml)

## [Stochastic Optimization Modeling](BioReactorTwoBatch/build_model_2stg.py)
**Unknown Demand (3 scenarios)**<br>

| Demand Scenarios | Prob |  A   | C   | R<sub>+</sub> |
| ---------------- | :---:| ---: | ---:| ---:|
| High Demand      | 25%  | 40   | 30  | 40  |
| More of the Same | 50%  | 30   | 30  | 30  |
| R+ Down C Up     | 25%  | 30   | 40  | 10  |
| AVERAGE	       |      |32.5  |32.5 |27.5 |

<img src="./docs/TwoPeriodModel.png" alt="pictorial" width="500"/><br>
Includes Functionality for Bleed Feed Production

- 3 Products [A, C, R<sub>+</sub>]
- 2 Bioreactors [ BR1, BR2 ]
- 2 Periods [P1, P2]
- Includes Functionality for Bleed Feed Production: Avoid New Setup Cost in 2nd Period, If Bleed-Feed is Selected
- Includes Stochastic Constraint: Probability of Meeting End Inventory Requirement $\geq$ 75%

#### Schedule Production for 2 Periods
<u>Maximize</u> Net Revenue

(Revenue net of Production Cost, Stockout Cost, and Inventory Cost)

While the following constraints are satisfied:

All prior problem contraints for

- Period 1 and
- All Period 2 Scenarios

In addition:

- *Bleed Feed Constraint*: Bleed feed available in period 2 only if same product was scheduled for period 1
- *End Inventory Constraint*: Probability of meeting end inventory requirements exceeds limit


See Full Model Data in [Data Dictionary](BioReactorTwoBatch/model_data_2stg.yml)
