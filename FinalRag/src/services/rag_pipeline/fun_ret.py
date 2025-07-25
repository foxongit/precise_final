# === FINAL: Agentic Formula Processor with AST Evaluation and Formula Change Detection ===
 
import json
import re
import ast
import operator
import sqlite3
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
 
# -----------------------------
# Data Class for Function Metadata
# -----------------------------
@dataclass
class FunctionMetadata:
    function_name: str
    formula: str
    parameters: List[str]
    parameter_types: Dict[str, str]
    aliases: List[str]
    created_at: str
    last_modified: str
    usage_count: int = 0
 
# -----------------------------
# Safe Expression Evaluator
# -----------------------------
class SafeFormulaEvaluator(ast.NodeVisitor):
    def __init__(self, variables: Dict[str, float]):
        self.variables = variables
        self.ops = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Pow: operator.pow,
        }
 
    def visit_BinOp(self, node):
        left = self.visit(node.left)
        right = self.visit(node.right)
        op = self.ops[type(node.op)]
        return op(left, right)
 
    def visit_Name(self, node):
        var = node.id.lower().strip("_")
        if var not in self.variables:
            raise ValueError(f"Unknown variable: {var}")
        return self.variables[var]
 
    def visit_Constant(self, node):
        return node.value
 
    def visit_Num(self, node):
        return node.n
 
    def visit_Expr(self, node):
        return self.visit(node.value)
 
    def visit_Module(self, node):
        return self.visit(node.body[0])
 
    def visit_Expression(self, node):
        return self.visit(node.body)
 
    def evaluate(self, expr: str) -> float:
        parsed_expr = ast.parse(expr, mode='eval')
        return self.visit(parsed_expr.body)
 
# -----------------------------
# Database to store functions
# -----------------------------
class FunctionDatabase:
    def __init__(self, db_path: str = "function4.db"):
        self.db_path = db_path
        self.init_database()
 
    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS functions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            function_name TEXT UNIQUE,
            formula TEXT,
            parameters TEXT,
            parameter_types TEXT,
            aliases TEXT,
            created_at TEXT,
            last_modified TEXT,
            usage_count INTEGER DEFAULT 0
        )''')
        conn.commit()
        conn.close()
 
    def save_function(self, metadata: FunctionMetadata):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
        INSERT OR REPLACE INTO functions
        (function_name, formula, parameters, parameter_types, aliases, created_at, last_modified, usage_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', (
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
 
# -----------------------------
# String similarity matcher
# -----------------------------
class SemanticMatcher:
    @staticmethod
    def similarity_score(str1: str, str2: str) -> float:
        return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()
 
# -----------------------------
# Agentic Formula Processor
# -----------------------------
class AgenticFormulaProcessor:
    def __init__(self):
        self.db = FunctionDatabase()
        self.matcher = SemanticMatcher()
 
    def _find_existing_function(self, function_name: str) -> Optional[FunctionMetadata]:
        func = self.db.get_function(function_name)
        if func:
            return func
        return self.db.find_by_alias(function_name)
 
    def process_request(self, sample_input: Dict[str, Any]) -> Dict[str, Any]:
        formula_str = sample_input['formula']
        function_name = sample_input['function_name']
        data_points = sample_input['data_points']
 
        normalized_data = {
            re.sub(r'[^a-zA-Z0-9_]', '', k.lower().replace(' ', '_')).strip('_'): v
            for k, v in data_points.items()
        }
        normalized_formula = re.sub(r'\s+', '_', formula_str.split('=')[-1].strip().lower())
        normalized_formula = re.sub(r'[^a-zA-Z0-9_()+\-*/.]', '', normalized_formula).strip("_")
 
        existing_function = self._find_existing_function(function_name)
 
        if existing_function:
            if existing_function.formula.strip().lower() != formula_str.strip().lower():
                suggested_name = f"{function_name}_{'_'.join(normalized_data.keys())}"
                return {
                    "status": "formula_mismatch",
                    "message": "Function exists but with a different formula.",
                    "existing_formula": existing_function.formula,
                    "new_formula": formula_str,
                    "suggested_name": suggested_name
                }
            else:
                try:
                    evaluator = SafeFormulaEvaluator(normalized_data)
                    result = evaluator.evaluate(normalized_formula)
                    existing_function.usage_count += 1
                    self.db.save_function(existing_function)
                    return {
                        "status": "success",
                        "result": result,
                        "used": existing_function.function_name
                    }
                except Exception as e:
                    return {"status": "exec_error", "error": str(e)}
 
        try:
            evaluator = SafeFormulaEvaluator(normalized_data)
            result = evaluator.evaluate(normalized_formula)
 
            metadata = FunctionMetadata(
                function_name=function_name,
                formula=formula_str,
                parameters=list(normalized_data.keys()),
                parameter_types={k: 'array' if isinstance(v, list) else 'scalar' for k, v in normalized_data.items()},
                aliases=[function_name],
                created_at=datetime.now().isoformat(),
                last_modified=datetime.now().isoformat(),
                usage_count=1
            )
 
            self.db.save_function(metadata)
            return {
                "status": "success",
                "result": result,
                "used": function_name
            }
 
        except Exception as e:
            return {"status": "exec_error", "error": str(e)}
 
# -----------------------------
# Test Example
# -----------------------------
def test_input():
    processor = AgenticFormulaProcessor()
 
    input_1 = {
        "function_name": "calculate_operating_cost",
        "formula": "Operating Cost = Fixed Cost + Variable Cost - taxes",
        "data_points": {
            "Fixed Cost": 100000,
            "Variable Cost": 450000,
            "taxes": 9000
        }
    }
    print(json.dumps(processor.process_request(input_1), indent=2))
 
    input_2 = {
        "function_name": "calculate_operating_cost",
        "formula": "Operating Cost = Fixed Cost * Variable Cost - taxes",
        "data_points": {
            "Fixed Cost": 100000,
            "Variable Cost": 450000,
            "taxes": 9000
        }
    }
    print(json.dumps(processor.process_request(input_2), indent=2))
 
    input_3 = {
        "function_name": "calculate_operating_cost",
        "formula": "Operating Cost = Fixed Cost * Variable Cost - taxes",
        "data_points": {
            "Fixed Cost": 190000,
            "Variable Cost": 250000,
            "taxes": 9000
        }
    }
    print(json.dumps(processor.process_request(input_3), indent=2))
 
 
if __name__ == "__main__":
    test_input()