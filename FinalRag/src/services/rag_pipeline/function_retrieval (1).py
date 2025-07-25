import json
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from difflib import SequenceMatcher
import sqlite3
from datetime import datetime

@dataclass
class FunctionMetadata:
    function_name: str
    formula: str
    parameters: List[str]
    parameter_types: Dict[str, str]  # parameter -> type (scalar/array)
    aliases: List[str]  # alternative names for this function
    created_at: str
    last_modified: str
    usage_count: int = 0

class FunctionDatabase:
    def __init__(self, db_path: str = "functions.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the SQLite database for storing functions"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS functions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            function_name TEXT UNIQUE,
            formula TEXT,
            parameters TEXT,  -- JSON string
            parameter_types TEXT,  -- JSON string
            aliases TEXT,  -- JSON string
            created_at TEXT,
            last_modified TEXT,
            usage_count INTEGER DEFAULT 0
        )
        ''')
        
        conn.commit()
        conn.close()
    
    def save_function(self, metadata: FunctionMetadata):
        """Save function metadata to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT OR REPLACE INTO functions 
        (function_name, formula, parameters, parameter_types, aliases, created_at, last_modified, usage_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            metadata.function_name,
            metadata.formula,
            json.dumps(metadata.parameters),
            json.dumps(metadata.parameter_types),
            json.dumps(metadata.aliases),
            metadata.created_at,
            metadata.last_modified,
            metadata.usage_count
        ))
        
        conn.commit()
        conn.close()
    
    def get_function(self, function_name: str) -> Optional[FunctionMetadata]:
        """Retrieve function metadata from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM functions WHERE function_name = ?', (function_name,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return FunctionMetadata(
                function_name=result[1],
                formula=result[2],
                parameters=json.loads(result[3]),
                parameter_types=json.loads(result[4]),
                aliases=json.loads(result[5]),
                created_at=result[6],
                last_modified=result[7],
                usage_count=result[8]
            )
        return None
    
    def find_by_alias(self, alias: str) -> Optional[FunctionMetadata]:
        """Find function by alias"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM functions')
        results = cursor.fetchall()
        conn.close()
        
        for result in results:
            aliases = json.loads(result[5])
            if alias.lower() in [a.lower() for a in aliases]:
                return FunctionMetadata(
                    function_name=result[1],
                    formula=result[2],
                    parameters=json.loads(result[3]),
                    parameter_types=json.loads(result[4]),
                    aliases=json.loads(result[5]),
                    created_at=result[6],
                    last_modified=result[7],
                    usage_count=result[8]
                )
        return None
    
    def get_all_functions(self) -> List[FunctionMetadata]:
        """Get all functions from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM functions')
        results = cursor.fetchall()
        conn.close()
        
        functions = []
        for result in results:
            functions.append(FunctionMetadata(
                function_name=result[1],
                formula=result[2],
                parameters=json.loads(result[3]),
                parameter_types=json.loads(result[4]),
                aliases=json.loads(result[5]),
                created_at=result[6],
                last_modified=result[7],
                usage_count=result[8]
            ))
        return functions

class FormulaParser:
    @staticmethod
    def extract_parameters(formula: str) -> Tuple[List[str], Dict[str, str]]:
        """Extract parameters from formula and determine their types"""
        # Find all variables in the formula
        pattern = r'\b[a-zA-Z_][a-zA-Z0-9_]*\b'
        variables = set(re.findall(pattern, formula))
        
        # Remove common math functions and operators
        reserved_words = {'sum', 'avg', 'max', 'min', 'abs', 'sqrt', 'log', 'exp', 'sin', 'cos', 'tan'}
        parameters = [var for var in variables if var not in reserved_words]
        
        # Determine parameter types based on formula context
        parameter_types = {}
        for param in parameters:
            if f'sum({param})' in formula or f'[' in formula:
                parameter_types[param] = 'array'
            else:
                parameter_types[param] = 'scalar'
        
        return parameters, parameter_types

class SemanticMatcher:
    @staticmethod
    def similarity_score(str1: str, str2: str) -> float:
        """Calculate similarity between two strings"""
        return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()
    
    @staticmethod
    def find_parameter_mappings(input_params: List[str], stored_params: List[str], threshold: float = 0.6) -> Dict[str, str]:
        """Find potential parameter mappings between input and stored parameters"""
        mappings = {}
        
        # Common financial term mappings
        semantic_mappings = {
            'revenue': ['income', 'sales', 'turnover'],
            'expenses': ['costs', 'expenditure', 'spending'],
            'profit': ['earnings', 'income_after_tax', 'net_income'],
            'operating_expenses': ['opex', 'operational_costs', 'operating_costs'],
            'miscellaneous_income': ['misc_income', 'other_income', 'additional_income']
        }
        
        for input_param in input_params:
            best_match = None
            best_score = 0
            
            for stored_param in stored_params:
                # Direct similarity
                score = SemanticMatcher.similarity_score(input_param, stored_param)
                
                # Check semantic mappings
                for key, values in semantic_mappings.items():
                    if input_param.lower() in values and stored_param.lower() == key:
                        score = max(score, 0.9)
                    elif stored_param.lower() in values and input_param.lower() == key:
                        score = max(score, 0.9)
                
                if score > best_score and score >= threshold:
                    best_score = score
                    best_match = stored_param
            
            if best_match:
                mappings[input_param] = best_match
        
        return mappings

class AgenticFormulaProcessor:
    def __init__(self):
        self.db = FunctionDatabase()
        self.parser = FormulaParser()
        self.matcher = SemanticMatcher()
    
    def process_request(self, sample_input: Dict[str, Any]) -> Dict[str, Any]:
        """Main processing function for the agentic flow"""
        formula = sample_input.get('formula', '')
        function_name = sample_input.get('function_name', '')
        data_points = sample_input.get('data_points', {})
        
        # Step 1: Check if function exists (Decision Box)
        existing_function = self._find_existing_function(function_name)
        
        if existing_function:
            # Function exists - handle edge cases
            return self._handle_existing_function(existing_function, sample_input)
        else:
            # Function doesn't exist - create new function
            return self._create_new_function(sample_input)
    
    def _find_existing_function(self, function_name: str) -> Optional[FunctionMetadata]:
        """Find existing function by name or alias"""
        # Try direct name match
        function = self.db.get_function(function_name)
        if function:
            return function
        
        # Try alias match
        function = self.db.find_by_alias(function_name)
        if function:
            return function
        
        # Try semantic similarity with all functions
        all_functions = self.db.get_all_functions()
        for func in all_functions:
            if self.matcher.similarity_score(function_name, func.function_name) > 0.8:
                return func
            
            # Check if any alias is similar
            for alias in func.aliases:
                if self.matcher.similarity_score(function_name, alias) > 0.8:
                    return func
        
        return None
    
    def _handle_existing_function(self, existing_function: FunctionMetadata, sample_input: Dict[str, Any]) -> Dict[str, Any]:
        """Handle cases where function already exists"""
        input_params = list(sample_input['data_points'].keys())
        stored_params = existing_function.parameters
        
        # Find parameter mappings
        mappings = self.matcher.find_parameter_mappings(input_params, stored_params)
        
        # Case 1: Parameters don't match at all
        if not mappings and set(input_params) != set(stored_params):
            return self._handle_parameter_mismatch(existing_function, sample_input)
        
        # Case 2: Some parameters match, some are extra
        if len(input_params) > len(stored_params):
            return self._handle_extra_parameters(existing_function, sample_input, mappings)
        
        # Case 3: Parameters match (with mappings)
        if mappings or set(input_params) == set(stored_params):
            return self._execute_with_mappings(existing_function, sample_input, mappings)
        
        # Default case: create new function
        return self._create_new_function(sample_input)
    
    def _handle_parameter_mismatch(self, existing_function: FunctionMetadata, sample_input: Dict[str, Any]) -> Dict[str, Any]:
        """Handle case where parameters don't match existing function"""
        return {
            "status": "parameter_mismatch",
            "message": f"Function '{existing_function.function_name}' exists but parameters don't match",
            "existing_parameters": existing_function.parameters,
            "input_parameters": list(sample_input['data_points'].keys()),
            "recommendation": "create_new_function_variant",
            "suggested_name": f"{sample_input['function_name']}_v2"
        }
    
    def _handle_extra_parameters(self, existing_function: FunctionMetadata, sample_input: Dict[str, Any], mappings: Dict[str, str]) -> Dict[str, Any]:
        """Handle case where input has extra parameters"""
        input_params = set(sample_input['data_points'].keys())
        mapped_params = set(mappings.keys())
        extra_params = input_params - mapped_params
        
        return {
            "status": "extra_parameters_detected",
            "message": f"Function '{existing_function.function_name}' found but input has additional parameters",
            "extra_parameters": list(extra_params),
            "parameter_mappings": mappings,
            "recommendation": "update_function_or_create_variant",
            "options": {
                "update_existing": "Add extra parameters to existing function",
                "create_variant": f"Create new function variant: {sample_input['function_name']}_extended"
            }
        }
    
    def _execute_with_mappings(self, existing_function: FunctionMetadata, sample_input: Dict[str, Any], mappings: Dict[str, str]) -> Dict[str, Any]:
        """Execute function with parameter mappings"""
        try:
            # Map input data to stored parameters
            mapped_data = {}
            for input_param, value in sample_input['data_points'].items():
                stored_param = mappings.get(input_param, input_param)
                mapped_data[stored_param] = value
            
            # Execute the formula
            result = self._evaluate_formula(existing_function.formula, mapped_data)
            
            # Update usage count
            existing_function.usage_count += 1
            self.db.save_function(existing_function)
            
            return {
                "status": "success",
                "result": result,
                "function_used": existing_function.function_name,
                "parameter_mappings": mappings,
                "formula": existing_function.formula
            }
        
        except Exception as e:
            return {
                "status": "execution_error",
                "error": str(e),
                "function": existing_function.function_name
            }
    
    def _create_new_function(self, sample_input: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new function"""
        try:
            formula = sample_input['formula']
            function_name = sample_input['function_name']
            data_points = sample_input['data_points']
            
            # Extract parameters from formula
            parameters, parameter_types = self.parser.extract_parameters(formula)
            
            # Create function metadata
            metadata = FunctionMetadata(
                function_name=function_name,
                formula=formula,
                parameters=parameters,
                parameter_types=parameter_types,
                aliases=[function_name],
                created_at=datetime.now().isoformat(),
                last_modified=datetime.now().isoformat(),
                usage_count=1
            )
            
            # Save to database
            self.db.save_function(metadata)
            
            # Execute the formula
            result = self._evaluate_formula(formula, data_points)
            
            return {
                "status": "new_function_created",
                "result": result,
                "function_name": function_name,
                "formula": formula,
                "parameters": parameters
            }
        
        except Exception as e:
            return {
                "status": "creation_error",
                "error": str(e)
            }
    
    def _evaluate_formula(self, formula: str, data_points: Dict[str, Any]) -> float:
        """Safely evaluate the formula with given data points"""
        try:
            # Replace variables in formula with actual values
            working_formula = formula
            
            for param, value in data_points.items():
                if isinstance(value, list):
                    # Handle array parameters
                    if f'sum({param})' in working_formula:
                        working_formula = working_formula.replace(f'sum({param})', str(sum(value)))
                    elif f'avg({param})' in working_formula:
                        working_formula = working_formula.replace(f'avg({param})', str(sum(value) / len(value)))
                    elif f'max({param})' in working_formula:
                        working_formula = working_formula.replace(f'max({param})', str(max(value)))
                    elif f'min({param})' in working_formula:
                        working_formula = working_formula.replace(f'min({param})', str(min(value)))
                else:
                    # Handle scalar parameters
                    working_formula = working_formula.replace(param, str(value))
            
            # Safe evaluation (restricted to basic math operations)
            allowed_names = {
                "__builtins__": {},
                "abs": abs, "min": min, "max": max, "sum": sum,
                "round": round, "pow": pow
            }
            
            result = eval(working_formula, allowed_names, {})
            return float(result)
        
        except Exception as e:
            raise ValueError(f"Formula evaluation failed: {str(e)}")
    
    def add_function_alias(self, function_name: str, alias: str) -> bool:
        """Add an alias to an existing function"""
        function = self.db.get_function(function_name)
        if function:
            if alias not in function.aliases:
                function.aliases.append(alias)
                function.last_modified = datetime.now().isoformat()
                self.db.save_function(function)
                return True
        return False

# Example usage and testing
def test_agentic_processor():
    processor = AgenticFormulaProcessor()
    
    # Test case 1: New function
    sample_input_1 = {
        "formula": "operating_expenses + sum(miscellaneous_income)",
        "function_name": "calculate_revenue",
        "data_points": {
            "operating_expenses": 30000,
            "miscellaneous_income": [1000, 2000]
        }
    }
    
    result1 = processor.process_request(sample_input_1)
    print("Test 1 - New Function:")
    print(json.dumps(result1, indent=2))
    print()
    
    # Test case 2: Same function with different parameter names
    sample_input_2 = {
        "formula": "profit + sum(expenditure)",
        "function_name": "calculate_revenue",
        "data_points": {
            "profit": 30000,
            "expenditure": [1000, 2000]
        }
    }
    
    result2 = processor.process_request(sample_input_2)
    print("Test 2 - Different Parameter Names:")
    print(json.dumps(result2, indent=2))
    print()
    
    # Test case 3: Same function with extra parameters
    sample_input_3 = {
        "formula": "operating_expenses + sum(miscellaneous_income) - taxes",
        "function_name": "calculate_revenue",
        "data_points": {
            "operating_expenses": 30000,
            "miscellaneous_income": [1000, 2000, 500],
            "taxes": 5000
        }
    }
    
    result3 = processor.process_request(sample_input_3)
    print("Test 3 - Extra Parameters:")
    print(json.dumps(result3, indent=2))
    print()

if __name__ == "__main__":
    test_agentic_processor()