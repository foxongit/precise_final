from src.core.config import settings
import requests

# --- Prompt Builder ---
def prepare_messages(user_query, masked_text):
    return [
        {
            "role": "system",
            "content": """You are a financial data extraction expert. Extract financial data and formulas from the given text into a strictly formatted JSON response.
 
Input:
- User query asking about financial calculations
- Text with masked numbers (MONEY_1, PERCENT_1, etc. format)
 
Output Requirements:
IMPORTANT: Respond ONLY with a valid JSON object containing exactly these fields:
{
    "title": "brief description of calculation",
    "formula": "mathematical formula using variable names",
    "variables": {
        "variable_name": "MONEY_1 or other masked value"
    },
    "computeNeeded": "True or False"
}
 
Critical Rules:
1. Use EXACT masked values and ALWAYS wrap them in quotes: "MONEY_1", "PERCENT_1"
2. Use proper JSON syntax:
   - Use double quotes for ALL strings, including masked values
   - Every MONEY_X, PERCENT_X must be in quotes like "MONEY_1"
   - No trailing commas
   - No comments
   - No line breaks in values
3. Keep formulas simple and clear
4. CRITICAL: ALL variables used in the formula MUST be present in the variables object
5. CRITICAL: NO extra variables should be in the variables object that aren't used in the formula
6. CRITICAL: ALL calculations must be done within the formula itself - no separate computation steps
7. Variables must match the formula exactly - every variable in formula must have corresponding entry in variables
8. IMPORTANT: Never use bare MONEY_X values - always use "MONEY_X"
9. IMPORTANT: computeNeeded must be "True" if query requires computation based on Masked Chunks, "False" if it does not
 
Example of CORRECT JSON response:
{
    "title": "Net Revenue Calculation",
    "formula": "gross_revenue - total_expenses",
    "variables": {
        "gross_revenue": "MONEY_1",
        "total_expenses": "MONEY_2"
    },
    "computeNeeded": "True"
}
 
Example of INCORRECT response (missing quotes around MONEY values):
{
    "title": "Net Revenue Calculation",
    "formula": "gross_revenue - total_expenses",
    "variables": {
        "gross_revenue": MONEY_1,
        "total_expenses": MONEY_2
    },
    "computeNeeded": "True"
}
 
Example of CORRECT response with complex calculation:
{
    "title": "ROI Percentage Calculation",
    "formula": "((revenue - cost) / cost) * 100",
    "variables": {
        "revenue": "MONEY_1",
        "cost": "MONEY_2"
    },
    "computeNeeded": "True"
}
 
Example of INCORRECT response (extra variable not used in formula):
{
    "title": "Net Profit",
    "formula": "revenue - expenses",
    "variables": {
        "revenue": "MONEY_1",
        "expenses": "MONEY_2",
        "tax_rate": "PERCENT_1"
    },
    "computeNeeded": "True"
}
 
DO NOT:
- Add explanations or notes
- Use single quotes
- Modify masked values
- Include additional fields
- Include line breaks in values
 
ONLY OUTPUT VALID JSON."""
        },
        {
            "role": "user",
            "content": f"""Query: {user_query}
 
Here is the masked data:
 
{masked_text}"""
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