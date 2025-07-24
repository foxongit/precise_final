from src.core.config import settings
import requests

# --- Prompt Builder ---
def prepare_messages(user_query, masked_text):
    return [
        {
            "role": "system",
            "content": """You are an expert financial data extraction and analysis system. Your task is to analyze financial text and extract relevant data for calculations based on user queries.

## INPUT FORMAT:
- User Query: A question about financial calculations or data analysis
- Masked Text: Financial document with sensitive values replaced by placeholders (MONEY_1, PERCENT_1, NUMBER_1, etc.)

## OUTPUT FORMAT:
Respond with ONLY a valid JSON object following this exact structure:

```json
{
    "title": "Brief descriptive title of the calculation",
    "formula": "Mathematical expression using variable names",
    "variables": {
        "variable_name": "MASKED_VALUE"
    },
    "computeNeeded": "True",
    "confidence": "High"
}
```

## CRITICAL FORMATTING RULES:

### JSON Syntax:
- Use double quotes for ALL strings
- All masked values MUST be wrapped in quotes: "MONEY_1", "PERCENT_1", "NUMBER_1"
- No trailing commas
- No comments or additional text
- No line breaks within string values

### Variable Handling:
- Variable names should be descriptive (e.g., "revenue", "operating_expenses", "tax_rate")
- Each variable must map to exactly one masked placeholder
- For arrays of values, use JSON array syntax: ["MONEY_1", "MONEY_2", "MONEY_3"]

### Formula Construction:
- Use standard mathematical operators: +, -, *, /, ^, ()
- For complex operations, use function notation: sum(), average(), max(), min()
- Keep formulas readable and mathematically correct

### Field Definitions:
- title: Concise description (max 50 characters)
- formula: Mathematical expression using variable names from the variables object
- variables: Object mapping descriptive names to masked placeholders
- computeNeeded: "True" if calculation required, "False" if only data extraction
- confidence: "High", "Medium", or "Low" based on data clarity

## EXAMPLES:

### Example 1 - Simple Calculation:
```json
{
    "title": "Net Profit Margin",
    "formula": "(net_income / total_revenue) * 100",
    "variables": {
        "net_income": "MONEY_1",
        "total_revenue": "MONEY_2"
    },
    "computeNeeded": "True",
    "confidence": "High"
}
```

### Example 2 - Multiple Values:
```json
{
    "title": "Total Operating Expenses",
    "formula": "sum(expense_items)",
    "variables": {
        "expense_items": ["MONEY_1", "MONEY_2", "MONEY_3", "MONEY_4"]
    },
    "computeNeeded": "True",
    "confidence": "High"
}
```

### Example 3 - Mixed Data Types:
```json
{
    "title": "ROI Calculation",
    "formula": "((current_value - initial_investment) / initial_investment) * 100",
    "variables": {
        "current_value": "MONEY_1",
        "initial_investment": "MONEY_2"
    },
    "computeNeeded": "True",
    "confidence": "Medium"
}
```

### Example 4 - Data Extraction Only:
```json
{
    "title": "Current Cash Balance",
    "formula": "cash_balance",
    "variables": {
        "cash_balance": "MONEY_1"
    },
    "computeNeeded": "False",
    "confidence": "High"
}
```

## ERROR PREVENTION:
- Never modify or interpret masked values (keep "MONEY_1" as "MONEY_1")
- Ensure all variables in formula exist in variables object
- Use proper JSON escaping for special characters
- Validate mathematical syntax in formulas

## EDGE CASES:
- If data is insufficient: Set confidence to "Low" and note in title
- If multiple interpretations possible: Choose the most logical based on context
- If no calculation needed: Set computeNeeded to "False"
- If masked values are unclear: Use generic variable names but maintain mapping

Remember: Output ONLY the JSON object. No explanations, comments, or additional text."""
        },
        {
            "role": "user",
            "content": f"""Query: {user_query}

Masked Financial Data:
{masked_text}

Please analyze the above data and provide the JSON response for the requested financial calculation or data extraction."""
        }
    ]

def call_llm(user_query, masked_text, llm):
    """
    Call the LLM using the initialized LLM instance from the pipeline
    
    Args:
        user_query (str): The user's financial query
        masked_text (str): Financial text with masked sensitive values
        llm: Initialized LangChain LLM instance
    
    Returns:
        str: JSON response from the LLM or None if error occurs
    """
    try:
        messages = prepare_messages(user_query, masked_text)
        
        # Convert to LangChain message format
        from langchain_core.messages import SystemMessage, HumanMessage
        
        langchain_messages = [
            SystemMessage(content=messages[0]["content"]),
            HumanMessage(content=messages[1]["content"])
        ]
        
        # Invoke the LLM with error handling
        response = llm.invoke(langchain_messages)
        
        # Validate response is not empty
        if not response or not response.content:
            print("Warning: Empty response from LLM")
            return None
            
        return response.content.strip()
        
    except Exception as e:
        print(f"Error calling LLM: {str(e)}")
        # Log more details for debugging
        print(f"Query: {user_query[:100]}...")
        print(f"Masked text length: {len(masked_text) if masked_text else 0}")
        return None

def validate_llm_response(response_text):
    """
    Validate that the LLM response is properly formatted JSON
    
    Args:
        response_text (str): Raw response from LLM
    
    Returns:
        dict: Parsed JSON object or None if invalid
    """
    try:
        import json
        
        # Clean the response (remove markdown code blocks if present)
        cleaned_response = response_text.strip()
        if cleaned_response.startswith('```json'):
            cleaned_response = cleaned_response[7:]
        if cleaned_response.endswith('```'):
            cleaned_response = cleaned_response[:-3]
        cleaned_response = cleaned_response.strip()
        
        # Parse JSON
        parsed_json = json.loads(cleaned_response)
        
        # Validate required fields
        required_fields = ['title', 'formula', 'variables', 'computeNeeded']
        for field in required_fields:
            if field not in parsed_json:
                print(f"Missing required field: {field}")
                return None
        
        return parsed_json
        
    except json.JSONDecodeError as e:
        print(f"JSON parsing error: {str(e)}")
        print(f"Response text: {response_text[:200]}...")
        return None
    except Exception as e:
        print(f"Validation error: {str(e)}")
        return None

# Legacy compatibility function
def llm_answerer_func(context_data, llm):
    """
    Legacy function for compatibility with existing pipeline
    
    Args:
        context_data (dict): Dictionary containing 'query' and 'context' keys
        llm: LangChain LLM instance
    
    Returns:
        str: JSON response from LLM
    """
    query = context_data.get("query", "")
    context = context_data.get("context", "")
    
    if not query:
        print("Warning: Empty query provided")
        return None
    
    response = call_llm(query, context, llm)
    
    # Optionally validate the response
    if response:
        validated = validate_llm_response(response)
        if not validated:
            print("Warning: LLM response failed validation")
    
    return response