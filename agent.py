from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

class Agent:
    """A Agent that answers basic questions"""
    
    def __init__(self, tools):
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")
        
        if openrouter_key:
            self.client = OpenAI(
                base_url= "https://openrouter.ai/api/v1",
                api_key= openrouter_key,
            )
        elif openai_key:
            self.client = OpenAI(api_key=openai_key)
        else:
            raise RuntimeError("PLease add any of the 2 API keys in the .env file.")
        
        #Now we include the models.
        self.model= os.getenv("MODEL", "gpt-4o-mini")
        self.system_message = (
            "You are one of the most intelligent Assistant in human history, capable to break down even the most hardest and complicated tasks into very easy points"
        )
        self.tools = tools
        self.tool_map = {tool.get_schema()["function"]["name"]: tool for tool in tools}
        self.messages = []
        
    def _get_tool_schemas(self):
        """Extract Schemas From All Tools"""
        return [tool.get_schema() for tool in self.tools]
        
        
        
    def chat(self, message):
        """Processes user messages and gives back a response"""
        
        # First we save the user's inputs into the short memory

        if message is not None and str(message).strip():
            self.messages.append({"role": "user", "content": message})
        payload = [{"role": "system", "content": self.system_message}] + self.messages
        
        respond = self.client.chat.completions.create(
            model= self.model, 
            max_tokens=1024,
            tools = self._get_tool_schemas() if self.tools else None,
            messages= payload,
            temperature= 0.1
        )
        
        # Now we save the Assistant's response/output into the short term memory
        return respond
    
        







