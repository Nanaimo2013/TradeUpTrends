from typing import List, Dict, Any
import logging
from dataclasses import dataclass
from statistics import mean

logger = logging.getLogger(__name__)

@dataclass
class TradeUpContract:
    input_items: List[Dict[str, Any]]
    potential_outputs: List[Dict[str, Any]]
    cost: float
    expected_value: float
    profit_margin: float
    risk_level: str
    float_range: tuple
    success_chance: float

class TradeUpCalculator:
    def __init__(self, config: Dict):
        self.config = config
        self.rarity_levels = config['analysis']['trade_up_rules']['rarity_levels']
        
    def _get_next_rarity(self, current_rarity: str) -> str:
        """Get the next rarity level up."""
        try:
            current_index = self.rarity_levels.index(current_rarity)
            if current_index < len(self.rarity_levels) - 1:
                return self.rarity_levels[current_index + 1]
        except ValueError:
            pass
        return None

    def _calculate_float_value(self, min_float: float, max_float: float, wear_value: str) -> float:
        """Calculate the float value based on wear."""
        wear_ranges = self.config['analysis']['wear_ranges']
        if wear_value in wear_ranges:
            wear_min, wear_max = wear_ranges[wear_value]
            return min_float + (max_float - min_float) * ((wear_min + wear_max) / 2)
        return (min_float + max_float) / 2

    def _calculate_success_chance(self, input_items: List[Dict[str, Any]], target_float: float) -> float:
        """Calculate the chance of getting desired float value."""
        input_floats = [self._calculate_float_value(0, 1, item['wear']) for item in input_items]
        avg_float = mean(input_floats)
        float_diff = abs(avg_float - target_float)
        
        if float_diff <= self.config['analysis']['trade_up_rules']['min_float_difference']:
            return 0.95
        elif float_diff <= self.config['analysis']['trade_up_rules']['max_float_difference']:
            return 0.75
        return 0.5

    def _get_risk_level(self, profit_margin: float, success_chance: float) -> str:
        """Determine risk level of trade-up contract."""
        if profit_margin < 0:
            return "High Risk"
        if profit_margin > 50 and success_chance > 0.8:
            return "Low Risk"
        if profit_margin > 20 and success_chance > 0.6:
            return "Medium Risk"
        return "High Risk"

    def find_trade_up_opportunities(self, items: List[Dict[str, Any]]) -> List[TradeUpContract]:
        """Find profitable trade-up contract opportunities."""
        opportunities = []
        
        # Group items by rarity
        rarity_groups = {}
        for item in items:
            rarity = self._get_item_rarity(item['name'])
            if rarity not in rarity_groups:
                rarity_groups[rarity] = []
            rarity_groups[rarity].append(item)

        # Analyze each rarity group
        for rarity, items_group in rarity_groups.items():
            next_rarity = self._get_next_rarity(rarity)
            if not next_rarity:
                continue

            # Find potential output items
            potential_outputs = [item for item in items if self._get_item_rarity(item['name']) == next_rarity]
            if not potential_outputs:
                continue

            # Find possible input combinations
            input_combinations = self._find_input_combinations(items_group)
            
            for inputs in input_combinations:
                cost = sum(float(item['price'].replace('$', '').replace(',', '')) for item in inputs)
                if cost > self.config['analysis']['max_price']:
                    continue

                # Calculate expected value
                exp_value = self._calculate_expected_value(inputs, potential_outputs)
                profit_margin = ((exp_value - cost) / cost) * 100

                if profit_margin >= self.config['analysis']['min_profit_margin']:
                    # Calculate float range and success chance
                    target_float = self._calculate_float_value(0, 1, "Factory New")
                    success_chance = self._calculate_success_chance(inputs, target_float)
                    float_range = (min(self._calculate_float_value(0, 1, item['wear']) for item in inputs),
                                 max(self._calculate_float_value(0, 1, item['wear']) for item in inputs))

                    contract = TradeUpContract(
                        input_items=inputs,
                        potential_outputs=potential_outputs,
                        cost=cost,
                        expected_value=exp_value,
                        profit_margin=profit_margin,
                        risk_level=self._get_risk_level(profit_margin, success_chance),
                        float_range=float_range,
                        success_chance=success_chance
                    )
                    opportunities.append(contract)

        return sorted(opportunities, key=lambda x: x.profit_margin, reverse=True)

    def _get_item_rarity(self, item_name: str) -> str:
        """Determine item rarity based on name and market data."""
        # This is a simplified version - you would want to implement proper rarity detection
        if "Covert" in item_name:
            return "Covert"
        if "Classified" in item_name:
            return "Classified"
        if "Restricted" in item_name:
            return "Restricted"
        return "Mil-Spec"

    def _find_input_combinations(self, items: List[Dict[str, Any]], max_items: int = 10) -> List[List[Dict[str, Any]]]:
        """Find valid combinations of input items for trade-up contracts."""
        from itertools import combinations
        valid_combinations = []
        
        # Try different numbers of input items
        for n in range(max_items, max_items + 1):
            for combo in combinations(items, n):
                if self._is_valid_combination(combo):
                    valid_combinations.append(list(combo))
                
                if len(valid_combinations) >= 100:  # Limit number of combinations to analyze
                    break
                    
        return valid_combinations

    def _is_valid_combination(self, items: List[Dict[str, Any]]) -> bool:
        """Check if a combination of items is valid for trade-up."""
        if not items:
            return False
            
        # Check if all items are of the same rarity
        first_rarity = self._get_item_rarity(items[0]['name'])
        if not all(self._get_item_rarity(item['name']) == first_rarity for item in items):
            return False
            
        # Check total cost
        total_cost = sum(float(item['price'].replace('$', '').replace(',', '')) for item in items)
        if total_cost > self.config['analysis']['max_price']:
            return False
            
        return True

    def _calculate_expected_value(self, inputs: List[Dict[str, Any]], potential_outputs: List[Dict[str, Any]]) -> float:
        """Calculate expected value of trade-up contract."""
        if not potential_outputs:
            return 0.0
            
        # Calculate average price of potential outputs
        output_prices = [float(item['price'].replace('$', '').replace(',', '')) for item in potential_outputs]
        return sum(output_prices) / len(output_prices)

    def get_trade_up_summary(self, contract: TradeUpContract) -> Dict[str, Any]:
        """Get a detailed summary of a trade-up contract."""
        return {
            "input_cost": contract.cost,
            "expected_value": contract.expected_value,
            "profit_margin": contract.profit_margin,
            "risk_level": contract.risk_level,
            "success_chance": contract.success_chance,
            "float_range": contract.float_range,
            "input_items": [{"name": item["name"], "wear": item["wear"], "price": item["price"]} 
                          for item in contract.input_items],
            "potential_outputs": [{"name": item["name"], "wear": item["wear"], "price": item["price"]} 
                                for item in contract.potential_outputs]
        } 