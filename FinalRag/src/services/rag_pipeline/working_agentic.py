import sqlite3
import json
import logging
import re
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import statistics
import math
import os
from difflib import SequenceMatcher
# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('AgenticFormulaSystem')

class AgenticFormulaSystem:
    def __init__(self, db_path: str = "functions11.db"):
        """Initialize the Agentic Formula System with fixed database schema"""
        self.db_path = db_path
        self.client = None

        self._update_database_schema()
        self._init_database()

        logger.info("=== Agentic Formula System Initialized ===")
        logger.info(f"Database: [OK]")

    def _init_database(self):
        """Initialize database with correct schema including calculation_type column and scaling results"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create functions table with all required columns
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS functions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    formula TEXT NOT NULL,
                    parameters TEXT NOT NULL,
                    calculation_type TEXT DEFAULT 'general',
                    description TEXT,
                    aliases TEXT DEFAULT '[]',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    usage_count INTEGER DEFAULT 0
                )
            ''')
            
            # Create scaling_results table for storing scaled results
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scaling_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    function_id INTEGER,
                    execution_id TEXT NOT NULL,
                    original_result REAL NOT NULL,
                    scale_factor_a REAL NOT NULL,
                    offset_b REAL NOT NULL,
                    scaled_result REAL NOT NULL,
                    variables TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (function_id) REFERENCES functions (id)
                )
            ''')
            
            # Check if calculation_type column exists, add if missing
            cursor.execute("PRAGMA table_info(functions)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'calculation_type' not in columns:
                cursor.execute('ALTER TABLE functions ADD COLUMN calculation_type TEXT DEFAULT "general"')
                logger.info("Added missing calculation_type column")
            
            if 'aliases' not in columns:
                cursor.execute('ALTER TABLE functions ADD COLUMN aliases TEXT DEFAULT "[]"')
                logger.info("Added missing aliases column")
            
            conn.commit()
            conn.close()
            logger.info("Database schema created/verified")
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise
    
    def _update_database_schema(self):
        """Update database schema to include missing columns"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if description column exists
            cursor.execute("PRAGMA table_info(functions)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'description' not in columns:
                logging.info("Adding missing 'description' column to functions table")
                cursor.execute("ALTER TABLE functions ADD COLUMN description TEXT")
                conn.commit()
                
        except sqlite3.Error as e:
            logging.error(f"Database schema update failed: {e}")
        finally:
            conn.close()
        
    def _extract_parameters(self, formula: str) -> Dict[str, str]:
        """Extract parameters from formula and infer their types"""
        # Find all variable names in the formula
        variables = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', formula)
        
        # Remove function names
        functions = ['sum', 'avg', 'max', 'min', 'abs', 'sqrt', 'log', 'exp', 'sin', 'cos', 'tan']
        variables = [var for var in variables if var not in functions]
        
        # Infer types based on context
        parameters = {}
        for var in set(variables):
            if any(func in formula for func in ['sum(', 'avg(', 'max(', 'min(']) and var in formula:
                # Check if this variable is used with aggregate functions
                if f'({var})' in formula or f'( {var})' in formula:
                    parameters[var] = 'list'
                else:
                    parameters[var] = 'float'
            else:
                parameters[var] = 'float'
        
        return parameters
    
    def _generate_function_name(self, formula: str, parameters: Dict[str, str]) -> str:
        """Generate a descriptive function name"""
        # Extract key terms from formula
        terms = []
        
        # Add calculation type prefix based on formula content
        if any(op in formula for op in ['sum(', 'avg(', 'max(', 'min(']):
            terms.append('analyze')
        elif any(op in formula for op in ['*', '**', 'exp']):
            terms.append('calculate')
        else:
            terms.append('compute')
        
        # Add main parameter names
        terms.extend(list(parameters.keys())[:3])  # Limit to 3 main parameters
        
        return '_'.join(terms)
    
    def save_function(self, name, formula, parameters, description=None, aliases=None):
        try:
            if aliases is None:
                aliases = [name]  # Default alias is the function name itself
                
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO functions 
                (name, formula, parameters, description, aliases, created_at, usage_count)
                VALUES (?, ?, ?, ?, ?, datetime('now'), 0)
            ''', (name, formula, json.dumps(parameters), description, json.dumps(aliases)))
            
            conn.commit()
            logging.info(f"Function '{name}' saved successfully")
            
        except sqlite3.Error as e:
            logging.error(f"Failed to save function: {e}")
            raise
        finally:
            conn.close()

    def _find_existing_function_by_name(self, function_name: str) -> Optional[Dict[str, Any]]:
        """Find an existing function by exact name match"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM functions WHERE name = ?', (function_name,))
            row = cursor.fetchone()
            
            if row:
                # Get column names
                cursor.execute("PRAGMA table_info(functions)")
                columns = [column[1] for column in cursor.fetchall()]
                
                func_dict = dict(zip(columns, row))
                # Parse JSON fields safely
                try:
                    func_dict['parameters'] = json.loads(func_dict['parameters'])
                    func_dict['aliases'] = json.loads(func_dict.get('aliases', '[]'))
                except (json.JSONDecodeError, TypeError):
                    func_dict['parameters'] = {}
                    func_dict['aliases'] = [function_name]
                
                conn.close()
                return func_dict
            
            conn.close()
            return None
            
        except Exception as e:
            logger.error(f"Failed to find function by name: {e}")
            return None

    def _find_existing_function_by_alias(self, alias: str) -> Optional[Dict[str, Any]]:
        """Find an existing function by alias"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM functions')
            rows = cursor.fetchall()
            
            # Get column names
            cursor.execute("PRAGMA table_info(functions)")
            columns = [column[1] for column in cursor.fetchall()]
            
            conn.close()
            
            for row in rows:
                func_dict = dict(zip(columns, row))
                try:
                    aliases = json.loads(func_dict.get('aliases', '[]'))
                    if alias.lower() in [a.lower() for a in aliases]:
                        func_dict['parameters'] = json.loads(func_dict['parameters'])
                        func_dict['aliases'] = aliases
                        return func_dict
                except (json.JSONDecodeError, TypeError):
                    continue
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to find function by alias: {e}")
            return None

    def _find_existing_function(self, function_name: str) -> Optional[Dict[str, Any]]:
        """Find existing function by name or alias"""
        # First try exact name match
        func = self._find_existing_function_by_name(function_name)
        if func:
            return func
        
        # Then try alias match
        return self._find_existing_function_by_alias(function_name)

    def _check_formula_conflict(self, existing_function: Dict[str, Any], new_formula: str) -> bool:
        """Check if the new formula conflicts with existing function formula - enhanced with semantic understanding"""
        existing_formula = existing_function.get('formula', '').strip().lower()
        new_formula_clean = new_formula.strip().lower()
        
        # Direct comparison first
        if existing_formula == new_formula_clean:
            return False
        
        # Enhanced semantic formula comparison
        return not self._are_formulas_semantically_equivalent(existing_formula, new_formula_clean)
    
    def _are_formulas_semantically_equivalent(self, formula1: str, formula2: str) -> bool:
        """Check if two formulas are semantically equivalent"""
        # Normalize formulas by extracting structure and parameter mappings
        structure1, params1 = self._extract_formula_structure(formula1)
        structure2, params2 = self._extract_formula_structure(formula2)
        
        # If structures are identical, check parameter mappings
        if structure1 == structure2:
            mappings = self._find_parameter_mappings(params2, params1, threshold=0.7)
            # Consider equivalent if we can map most parameters
            coverage = len(mappings) / len(params1) if params1 else 1
            return coverage >= 0.8
        
        return False
    
    def _extract_formula_structure(self, formula: str) -> tuple:
        """Extract the structural pattern of a formula and its parameters"""
        import re
        
        # Find all variable names
        variables = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', formula)
        functions = ['sum', 'avg', 'max', 'min', 'abs', 'sqrt', 'log', 'exp', 'sin', 'cos', 'tan']
        parameters = [var for var in variables if var not in functions]
        
        # Create structure by replacing parameters with placeholders
        structure = formula
        for i, param in enumerate(sorted(set(parameters))):
            structure = structure.replace(param, f'P{i}')
        
        return structure, list(set(parameters))

    def _increment_usage_count(self, function_name: str):
        """Increment the usage count for a function"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE functions 
                SET usage_count = usage_count + 1 
                WHERE name = ?
            ''', (function_name,))
            
            conn.commit()
            conn.close()
            logger.info(f"Incremented usage count for function '{function_name}'")
            
        except Exception as e:
            logger.error(f"Failed to increment usage count: {e}")

    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity score between two strings"""
        return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()

    def _find_similar_functions(self, formula: str, threshold: float = 0.85) -> List[Dict[str, Any]]:
        """Find functions with similar formulas"""
        try:
            existing_functions = self._get_functions()
            similar_functions = []
            
            for func in existing_functions:
                similarity = self._calculate_similarity(formula, func.get('formula', ''))
                if similarity >= threshold:
                    func['similarity_score'] = similarity
                    similar_functions.append(func)
            
            # Sort by similarity score (highest first)
            similar_functions.sort(key=lambda x: x.get('similarity_score', 0), reverse=True)
            return similar_functions
            
        except Exception as e:
            logger.error(f"Error finding similar functions: {e}")
            return []

    def _find_parameter_mappings(self, input_params: List[str], stored_params: List[str], threshold: float = 0.6) -> Dict[str, str]:
        """Find potential parameter mappings between input and stored parameters with semantic understanding"""
        mappings = {}
        
        # Enhanced semantic mappings for financial terms
        semantic_mappings = {
            'revenue': ['income', 'sales', 'turnover', 'receipts', 'earnings'],
            'expenses': ['costs', 'expenditure', 'spending', 'outflows', 'charges'],
            'profit': ['earnings', 'income_after_tax', 'net_income', 'surplus', 'gain'],
            'cost': ['expense', 'expenditure', 'outlay', 'charge', 'fee'],
            'operating_expenses': ['opex', 'operational_costs', 'operating_costs', 'running_costs'],
            'miscellaneous_income': ['misc_income', 'other_income', 'additional_income', 'sundry_income'],
            'tax': ['taxes', 'taxation', 'levy', 'duty'],
            'assets': ['holdings', 'property', 'resources', 'capital'],
            'liabilities': ['debts', 'obligations', 'payables', 'owing'],
            'equity': ['ownership', 'capital', 'net_worth', 'shareholders_equity']
        }
        
        for input_param in input_params:
            best_match = None
            best_score = 0
            
            for stored_param in stored_params:
                # Direct string similarity
                score = self._calculate_similarity(input_param, stored_param)
                
                # Check semantic mappings both ways
                for key, values in semantic_mappings.items():
                    # Input param is semantic equivalent of stored param
                    if input_param.lower() in values and stored_param.lower() == key:
                        score = max(score, 0.9)
                    # Stored param is semantic equivalent of input param
                    elif stored_param.lower() in values and input_param.lower() == key:
                        score = max(score, 0.9)
                    # Both are in same semantic group
                    elif input_param.lower() in values and stored_param.lower() in values:
                        score = max(score, 0.85)
                
                # Partial matching for compound terms
                input_words = input_param.lower().split('_')
                stored_words = stored_param.lower().split('_')
                
                common_words = set(input_words) & set(stored_words)
                if common_words and len(common_words) >= min(len(input_words), len(stored_words)) / 2:
                    partial_score = len(common_words) / max(len(input_words), len(stored_words))
                    score = max(score, partial_score * 0.8)
                
                if score > best_score and score >= threshold:
                    best_score = score
                    best_match = stored_param
            
            if best_match:
                mappings[input_param] = best_match
                logger.info(f"Parameter mapping: {input_param} -> {best_match} (score: {best_score:.2f})")
        
        return mappings

    def _enhanced_find_existing_function(self, function_name: str, formula: str, parameters: List[str]) -> Optional[Dict[str, Any]]:
        """Enhanced function finding with semantic similarity and parameter analysis"""
        # Step 1: Try exact name match
        func = self._find_existing_function_by_name(function_name)
        if func:
            return func
        
        # Step 2: Try alias match
        func = self._find_existing_function_by_alias(function_name)
        if func:
            return func
        
        # Step 3: Try semantic similarity with all functions
        all_functions = self._get_functions()
        for func in all_functions:
            # Check function name similarity
            name_similarity = self._calculate_similarity(function_name, func.get('name', ''))
            if name_similarity > 0.8:
                logger.info(f"Found function by name similarity: {func.get('name')} (score: {name_similarity:.2f})")
                return func
            
            # Check alias similarity
            aliases = func.get('aliases', [])
            if isinstance(aliases, str):
                try:
                    aliases = json.loads(aliases)
                except:
                    aliases = [aliases]
            
            for alias in aliases:
                alias_similarity = self._calculate_similarity(function_name, alias)
                if alias_similarity > 0.8:
                    logger.info(f"Found function by alias similarity: {alias} (score: {alias_similarity:.2f})")
                    return func
        
        # Step 4: Try formula similarity
        similar_functions = self._find_similar_functions(formula, threshold=0.85)
        if similar_functions:
            best_match = similar_functions[0]
            logger.info(f"Found function by formula similarity: {best_match.get('name')} (score: {best_match.get('similarity_score', 0):.2f})")
            return best_match
        
        return None

    def _execute_with_parameter_mapping(self, existing_function: Dict[str, Any], variables: Dict[str, Any]) -> Dict[str, Any]:
        """Execute function with automatic parameter mapping"""
        try:
            # Get stored parameters
            stored_params = existing_function.get('parameters', {})
            if isinstance(stored_params, str):
                try:
                    stored_params = json.loads(stored_params)
                except:
                    stored_params = {}
            
            input_params = list(variables.keys())
            stored_param_names = list(stored_params.keys())
            
            # Find parameter mappings
            mappings = self._find_parameter_mappings(input_params, stored_param_names)
            
            # Check if we have enough mappings
            if len(mappings) < len(stored_param_names) * 0.7:  # Need at least 70% parameter coverage
                return {
                    'status': 'parameter_mismatch',
                    'message': f"Insufficient parameter mappings found",
                    'required_parameters': stored_param_names,
                    'provided_parameters': input_params,
                    'mappings_found': mappings,
                    'coverage': f"{len(mappings)}/{len(stored_param_names)}"
                }
            
            # Map input data to stored parameters
            mapped_variables = {}
            for input_param, value in variables.items():
                mapped_param = mappings.get(input_param, input_param)
                mapped_variables[mapped_param] = value
                
            # Add any missing parameters with default values if possible
            for stored_param in stored_param_names:
                if stored_param not in mapped_variables:
                    # Try to find unmapped input parameter
                    unmapped_inputs = set(input_params) - set(mappings.keys())
                    if unmapped_inputs:
                        # Use the first unmapped parameter
                        unmapped_param = list(unmapped_inputs)[0]
                        mapped_variables[stored_param] = variables[unmapped_param]
                        logger.info(f"Auto-mapped remaining parameter: {unmapped_param} -> {stored_param}")
            
            # Execute the formula
            formula = existing_function.get('formula', '')
            result = self._evaluate_formula(formula, mapped_variables)
            
            return {
                'status': 'success',
                'result': result,
                'parameter_mappings': mappings,
                'mapped_variables': mapped_variables
            }
            
        except Exception as e:
            logger.error(f"Failed to execute with parameter mapping: {e}")
            return {
                'status': 'execution_error',
                'error': str(e)
            }

    def _handle_parameter_variations(self, existing_function: Dict[str, Any], 
                                   new_variables: Dict[str, Any], 
                                   new_formula: str) -> Dict[str, Any]:
        """Handle cases where function exists but with parameter variations"""
        
        stored_params = existing_function.get('parameters', {})
        if isinstance(stored_params, str):
            try:
                stored_params = json.loads(stored_params)
            except:
                stored_params = {}
        
        input_params = list(new_variables.keys())
        stored_param_names = list(stored_params.keys())
        
        # Find parameter mappings
        mappings = self._find_parameter_mappings(input_params, stored_param_names)
        
        # Case 1: Perfect parameter mapping (all parameters can be mapped)
        if len(mappings) == len(stored_param_names) and len(mappings) == len(input_params):
            logger.info("Perfect parameter mapping found - executing with mapped parameters")
            execution_result = self._execute_with_parameter_mapping(existing_function, new_variables)
            
            if execution_result.get('status') == 'success':
                return {
                    'action': 'reuse_with_mapping',
                    'function_name': existing_function.get('name'),
                    'parameter_mappings': mappings,
                    'execution_result': execution_result
                }
        
        # Case 2: Partial parameter mapping - input has extra parameters
        elif len(input_params) > len(stored_param_names):
            extra_params = set(input_params) - set(mappings.keys())
            return {
                'action': 'suggest_function_extension',
                'message': f"Function '{existing_function.get('name')}' can be extended with additional parameters",
                'existing_parameters': stored_param_names,
                'extra_parameters': list(extra_params),
                'suggested_name': f"{existing_function.get('name')}_extended",
                'parameter_mappings': mappings
            }
        
        # Case 3: Input has fewer parameters
        elif len(input_params) < len(stored_param_names):
            missing_params = set(stored_param_names) - set(mappings.values())
            return {
                'action': 'missing_parameters',
                'message': f"Function '{existing_function.get('name')}' requires additional parameters",
                'missing_parameters': list(missing_params),
                'provided_mappings': mappings
            }
        
        # Case 4: Same number of parameters but poor mapping
        else:
            return {
                'action': 'create_variant',
                'message': f"Parameters don't map well to existing function",
                'suggested_name': f"{existing_function.get('name')}_variant",
                'mapping_quality': f"{len(mappings)}/{len(stored_param_names)}"
            }

    def save_function_legacy(self, name, formula, parameters, description=None):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO functions 
                (name, formula, parameters, description, created_at, usage_count)
                VALUES (?, ?, ?, ?, datetime('now'), 0)
            ''', (name, formula, json.dumps(parameters), description))
            
            conn.commit()
            logging.info(f"Function '{name}' saved successfully")
            
        except sqlite3.Error as e:
            logging.error(f"Failed to save function: {e}")
            raise
        finally:
            conn.close()
    
    def _get_functions(self) -> List[Dict[str, Any]]:
        """Retrieve all functions from database with proper error handling"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM functions')
            rows = cursor.fetchall()
            
            # Get column names
            cursor.execute("PRAGMA table_info(functions)")
            columns = [column[1] for column in cursor.fetchall()]
            
            conn.close()
            
            functions = []
            for row in rows:
                func_dict = dict(zip(columns, row))
                # Parse parameters JSON safely
                try:
                    func_dict['parameters'] = json.loads(func_dict['parameters'])
                except (json.JSONDecodeError, TypeError):
                    func_dict['parameters'] = {}
                functions.append(func_dict)
            
            return functions
            
        except Exception as e:
            logger.error(f"Failed to retrieve functions: {e}")
            return []
    
    def get_all_functions(self) -> List[Dict[str, Any]]:
        """Public method to retrieve all functions from database"""
        return self._get_functions()
    
    def print_all_functions(self):
        """Print all functions in a formatted way"""
        functions = self.get_all_functions()
        
        if not functions:
            print("No functions found in the database.")
            return
        
        print(f"\n{'='*80}")
        print("📚 ALL FUNCTIONS IN DATABASE")
        print(f"{'='*80}")
        
        for i, func in enumerate(functions, 1):
            print(f"\n🔧 Function #{i}: {func['name']}")
            print(f"   📝 Formula: {func['formula']}")
            print(f"   📊 Parameters: {func['parameters']}")
            print(f"   🏷️ Type: {func.get('calculation_type', 'N/A')}")
            print(f"   📄 Description: {func.get('description', 'N/A')}")
            print(f"   📅 Created: {func.get('created_at', 'N/A')}")
            print(f"   🔄 Usage Count: {func.get('usage_count', 0)}")
            print(f"   🆔 ID: {func['id']}")
        
        print(f"\n📊 Total Functions: {len(functions)}")
        print(f"{'='*80}")
    
    def _apply_scaling(self, result: float, scale_factor_a: float = 1.0, offset_b: float = 0.0) -> float:
        # """Apply linear scaling transformation: ax + b"""
        scaled_result = scale_factor_a * result + offset_b
        logger.info(f"Scaling: {scale_factor_a} * {result} + {offset_b} = {scaled_result}")
        return scaled_result

    
    def _save_scaled_result(self, function_name: str, execution_id: str, original_result: float, 
                           scaled_result: float, scale_factor_a: float, offset_b: float,
                           variables: Dict[str, Any]) -> int:
        """Save scaled result to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get function ID
            cursor.execute('SELECT id FROM functions WHERE name = ?', (function_name,))
            function_row = cursor.fetchone()
            function_id = function_row[0] if function_row else None
            
            cursor.execute('''
                INSERT INTO scaling_results 
                (function_id, execution_id, original_result, scale_factor_a, offset_b, 
                 scaled_result, variables)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (function_id, execution_id, original_result, scale_factor_a, offset_b, 
                  scaled_result, json.dumps(variables)))
            
            result_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            logger.info(f"Scaled result saved with ID: {result_id}")
            return result_id
            
        except Exception as e:
            logger.error(f"Failed to save scaled result: {e}")
            raise
    
    def get_scaled_result(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve scaled result by execution ID"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT sr.*, f.name as function_name, f.formula 
                FROM scaling_results sr
                LEFT JOIN functions f ON sr.function_id = f.id
                WHERE sr.execution_id = ?
                ORDER BY sr.created_at DESC
                LIMIT 1
            ''', (execution_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'id': row[0],
                    'function_id': row[1],
                    'execution_id': row[2],
                    'original_result': row[3],
                    'scale_factor_a': row[4],
                    'offset_b': row[5],
                    'scaled_result': row[6],
                    'variables': json.loads(row[7]),
                    'created_at': row[8],
                    'function_name': row[9],
                    'formula': row[10]
                }
            return None
            
        except Exception as e:
            logger.error(f"Failed to retrieve scaled result: {e}")
            return None
    
    def get_all_scaled_results(self, function_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve all scaled results, optionally filtered by function name"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if function_name:
                cursor.execute('''
                    SELECT sr.*, f.name as function_name, f.formula 
                    FROM scaling_results sr
                    LEFT JOIN functions f ON sr.function_id = f.id
                    WHERE f.name = ?
                    ORDER BY sr.created_at DESC
                ''', (function_name,))
            else:
                cursor.execute('''
                    SELECT sr.*, f.name as function_name, f.formula 
                    FROM scaling_results sr
                    LEFT JOIN functions f ON sr.function_id = f.id
                    ORDER BY sr.created_at DESC
                ''')
            
            rows = cursor.fetchall()
            conn.close()
            
            results = []
            for row in rows:
                results.append({
                    'id': row[0],
                    'function_id': row[1],
                    'execution_id': row[2],
                    'original_result': row[3],
                    'scale_factor_a': row[4],
                    'offset_b': row[5],
                    'scaled_result': row[6],
                    'variables': json.loads(row[7]),
                    'created_at': row[8],
                    'function_name': row[9],
                    'formula': row[10]
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to retrieve scaled results: {e}")
            return []
    
    def _evaluate_formula(self, formula: str, variables: Dict[str, Any]) -> float:
        """Safely evaluate mathematical formula with given variables"""
        try:
            # Create a safe namespace for evaluation
            safe_dict = {
                '__builtins__': {},
                'abs': abs,
                'max': max,
                'min': min,
                'sum': sum,
                'avg': lambda x: statistics.mean(x),
                'sqrt': math.sqrt,
                'log': math.log,
                'exp': math.exp,
                'sin': math.sin,
                'cos': math.cos,
                'tan': math.tan,
                'pi': math.pi,
                'e': math.e
            }
            
            # Add variables to namespace
            safe_dict.update(variables)
            
            # Process lists with aggregate functions
            processed_formula = formula
            for var_name, var_value in variables.items():
                if isinstance(var_value, list):
                    # Replace aggregate function calls
                    if f'sum({var_name})' in processed_formula:
                        processed_formula = processed_formula.replace(f'sum({var_name})', str(sum(var_value)))
                    if f'avg({var_name})' in processed_formula:
                        processed_formula = processed_formula.replace(f'avg({var_name})', str(statistics.mean(var_value)))
                    if f'max({var_name})' in processed_formula:
                        processed_formula = processed_formula.replace(f'max({var_name})', str(max(var_value)))
                    if f'min({var_name})' in processed_formula:
                        processed_formula = processed_formula.replace(f'min({var_name})', str(min(var_value)))
            
            logger.info(f"Processed expression: {processed_formula}")
            
            # Evaluate the expression
            result = eval(processed_formula, safe_dict)
            return float(result)
            
        except Exception as e:
            logger.error(f"Formula evaluation failed: {e}")
            raise ValueError(f"Invalid formula or variables: {e}")
    
    def process_formula(self, formula: str, variables: Dict[str, Any], 
                       scale_factor_a: float = 2.0, offset_b: float = 0.0,
                       execution_id: Optional[str] = None) -> Dict[str, Any]:
        """Main method to process a formula request with scaling"""
        logger.info("=" * 50)
        logger.info("PROCESSING NEW FORMULA REQUEST")
        logger.info("=" * 50)
        
        # Generate execution ID if not provided
        if not execution_id:
            execution_id = f"exec_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        try:
            # Step 1: Analyze formula structure
            logger.info("Step 1: Analyzing formula structure")
            logger.info(f"Extracting parameters from formula: {formula}")
            parameters = self._extract_parameters(formula)
            logger.info(f"Extracted parameters: {parameters}")
            
            # Step 2: Check for existing functions with enhanced reuse logic
            logger.info("Step 2: Checking for existing functions with enhanced logic")
            function_name = self._generate_function_name(formula, parameters)
            logger.info(f"Generated function name for lookup: {function_name}")
            
            existing_function = self._enhanced_find_existing_function(function_name, formula, list(variables.keys()))
            
            if existing_function:
                logger.info(f"Found existing function: {existing_function['name']}")
                
                # Check for formula conflicts
                if self._check_formula_conflict(existing_function, formula):
                    # Formula conflict detected - auto-resolve by creating variant
                    suggested_name = f"{function_name}_v{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    logger.warning(f"Formula conflict detected. Auto-creating variant: {suggested_name}")
                    
                    # Create new function with suggested name to resolve conflict
                    calculation_type = 'financial' if any(term in formula.lower() for term in ['revenue', 'profit', 'cost', 'tax']) else 'general'
                    
                    try:
                        # Save new function with unique name
                        aliases = [suggested_name, function_name + "_conflict_resolved"]
                        self.save_function(suggested_name, formula, parameters, description=calculation_type, aliases=aliases)
                        logger.info(f"Created conflict-resolved function: {suggested_name}")
                        
                        # Evaluate formula with new function
                        original_result = self._evaluate_formula(formula, variables)
                        scaled_result = self._apply_scaling(original_result, scale_factor_a, offset_b)
                        
                        # Save scaled result
                        result_id = self._save_scaled_result(
                            suggested_name, execution_id, original_result, scaled_result,
                            scale_factor_a, offset_b, variables
                        )
                        
                        logger.info(f"Successfully resolved conflict and created function {suggested_name}")
                        
                        return {
                            'execution_id': execution_id,
                            'result_id': result_id,
                            'function_name': suggested_name,
                            'formula': formula,
                            'parameters': parameters,
                            'variables': variables,
                            'original_result': original_result,
                            'scaled_result': scaled_result,
                            'scale_factor_a': scale_factor_a,
                            'offset_b': offset_b,
                            'calculation_type': calculation_type,
                            'conflict_resolved': True,
                            'original_function': existing_function['name'],
                            'original_formula': existing_function['formula'],
                            'status': 'conflict_resolved'
                        }
                        
                    except Exception as e:
                        logger.error(f"Failed to resolve conflict: {e}")
                        return {
                            'status': 'formula_conflict',
                            'message': 'Function exists but with different formula - auto-resolution failed',
                            'existing_function': existing_function['name'],
                            'existing_formula': existing_function['formula'],
                            'new_formula': formula,
                            'suggested_name': suggested_name,
                            'execution_id': execution_id,
                            'conflict_detected': True,
                            'error': str(e)
                        }
                else:
                    # Handle parameter variations with enhanced logic
                    parameter_analysis = self._handle_parameter_variations(existing_function, variables, formula)
                    
                    if parameter_analysis.get('action') == 'reuse_with_mapping':
                        # Successfully mapped parameters - reuse function
                        logger.info("Reusing existing function with parameter mapping")
                        self._increment_usage_count(existing_function['name'])
                        
                        execution_result = parameter_analysis['execution_result']
                        original_result = execution_result['result']
                        scaled_result = self._apply_scaling(original_result, scale_factor_a, offset_b)
                        
                        # Save scaled result
                        result_id = self._save_scaled_result(
                            existing_function['name'], execution_id, original_result, scaled_result,
                            scale_factor_a, offset_b, variables
                        )
                        
                        logger.info(f"Successfully reused function {existing_function['name']} with parameter mapping")
                        
                        return {
                            'execution_id': execution_id,
                            'result_id': result_id,
                            'function_name': existing_function['name'],
                            'formula': existing_function['formula'],
                            'parameters': existing_function.get('parameters', {}),
                            'variables': variables,
                            'original_result': original_result,
                            'scaled_result': scaled_result,
                            'scale_factor_a': scale_factor_a,
                            'offset_b': offset_b,
                            'calculation_type': existing_function.get('calculation_type', 'general'),
                            'reused': True,
                            'parameter_mappings': parameter_analysis.get('parameter_mappings', {}),
                            'usage_count': existing_function.get('usage_count', 0) + 1
                        }
                    
                    elif parameter_analysis.get('action') in ['suggest_function_extension', 'missing_parameters', 'create_variant']:
                        # Parameter mismatch - return analysis for user decision
                        logger.warning(f"Parameter analysis suggests: {parameter_analysis.get('action')}")
                        parameter_analysis.update({
                            'execution_id': execution_id,
                            'status': 'parameter_analysis',
                            'existing_function': existing_function['name'],
                            'existing_formula': existing_function['formula']
                        })
                        return parameter_analysis
            
            # Step 3: Create new function if no existing function found
            logger.info("Step 3: Creating new function")
            calculation_type = 'financial' if any(term in formula.lower() for term in ['revenue', 'profit', 'cost', 'tax']) else 'general'
            
            # Step 4: Save new function
            logger.info("Step 4: Saving new function metadata")
            try:
                # Generate aliases (could include variations of the function name)
                aliases = [function_name]
                self.save_function(function_name, formula, parameters, description=calculation_type, aliases=aliases)
            except Exception as e:
                logger.warning(f"Failed to save function '{function_name}': {e}")
            
            # Step 5: Evaluate formula
            logger.info("Step 5: Evaluating formula")
            logger.info(f"Evaluating formula: {formula}")
            logger.info(f"With variables: {variables}")
            
            original_result = self._evaluate_formula(formula, variables)
            logger.info(f"Original evaluation result: {original_result}")
            
            # Step 6: Apply scaling
            logger.info("Step 6: Applying scaling transformation")
            logger.info(f"Scaling parameters: a={scale_factor_a}, b={offset_b}")
            scaled_result = self._apply_scaling(original_result, scale_factor_a, offset_b)
            logger.info(f"Scaled result: {scaled_result}")
            
            # Step 7: Save scaled result
            logger.info("Step 7: Saving scaled result")
            result_id = self._save_scaled_result(
                function_name, execution_id, original_result, scaled_result,
                scale_factor_a, offset_b, variables
            )
            
            logger.info(f"Successfully created and evaluated function {function_name}")
            logger.info(f"Original result: {original_result}")
            logger.info(f"Scaled result: {scaled_result}")
            logger.info(f"Execution ID: {execution_id}")
            
            # Return results
            return {
                'execution_id': execution_id,
                'result_id': result_id,
                'function_name': function_name,
                'formula': formula,
                'parameters': parameters,
                'variables': variables,
                'original_result': original_result,
                'scaled_result': scaled_result,
                'scale_factor_a': scale_factor_a,
                'offset_b': offset_b,
                'calculation_type': calculation_type
            }
            
        except Exception as e:
            logger.error(f"Formula processing failed: {e}")
            raise
        
        finally:
            logger.info("PROCESSING COMPLETE")
            logger.info("=" * 50)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get system statistics"""
        functions = self._get_functions()
        return {
            'total_functions': len(functions),
            'database_path': self.db_path,
            'function_types': {}
        }

# Example usage and testing
def main():
    print("✓ Agentic Formula System ready!")
    
    # Initialize system
    system = AgenticFormulaSystem()
    
    # Test examples
    examples = [
        {
            'title': 'Financial Calculation',
            'formula': 'revenue - sum(expenses)',
            'variables': {'revenue': 120000, 'expenses': [20000, 30000, 15000]}
        },
        {
            'title': 'Interest Calculation',
            'formula': 'principal * (1 + rate) ** years',
            'variables': {'principal': 10000, 'rate': 0.05, 'years': 3}
        },
        {
            'title': 'Data Aggregation',
            'formula': 'avg(scores) * weight_factor',
            'variables': {'scores': [85, 92, 78, 95, 88], 'weight_factor': 1.2}
        }
    ]
    
    for i, example in enumerate(examples, 1):
        print(f"\n{'='*60}")
        print(f"🧪 EXAMPLE {i}: {example['title']}")
        print(f"{'='*60}")

        try:
            result = system.process_formula(example['formula'], example['variables'])
            print(f"🔍 Processing Formula: {example['formula']}")
            print(f"🎯 Original Result: {result['original_result']}")
            print(f"📊 Scaled Result: {result['scaled_result']}")
            print(f"🏷️ Function Name: {result['function_name']}")
            print(f"🆔 Execution ID: {result['execution_id']}")
            
        except Exception as e:
            print(f"❌ Error: {e}")
    
    # Print statistics
    print(f"\n{'='*60}")
    print("📋 SYSTEM STATISTICS")
    print(f"{'='*60}")
    stats = system.get_statistics()
    print(f"📚 Total Functions: {stats['total_functions']}")
    print(f"💾 Database: {stats['database_path']}")
    
    # Display all functions in the database
    system.print_all_functions()

if __name__ == "__main__":
    main()