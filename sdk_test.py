import os
from dotenv import load_dotenv
from openai import AsyncOpenAI
import asyncio
from agents import Agent, Runner, function_tool, set_default_openai_client, set_tracing_disabled

load_dotenv()

custom_client = AsyncOpenAI(
    base_url= "https://openrouter.ai/api/v1",
    api_key= os.getenv("OPENROUTER_API_KEY")
)

set_default_openai_client(custom_client)
set_tracing_disabled(True)

@function_tool
def calculate(expression: str) -> str:
    """Calculate a mathematical expression and return the result"""
    
    try:
        result = eval(expression)
        return str(result)
    except:
        return "Invalid Expression"
    
    
agent = Agent(
    name = "Calculator Agent",
    model = "openai/gpt-4o-mini",
    instructions = "You are if not one of the best helpful assistant in the universe, use the calculate tool for any math",
    tools= [calculate] 
)

result = Runner.run_sync(agent, "What is 157.09 * 493.89?")
print(result.final_output)