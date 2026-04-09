from openai import OpenAI, APIStatusError
import os
from dotenv import load_dotenv

load_dotenv()

class Agent:
    """A Agent that answers basic questions"""
    
    def __init__(self, tools, model=None):
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")
        self.fallback_client = None
        self.fallback_model = None
        
        if openrouter_key:
            self.provider = "openrouter"
            self.client = OpenAI(
                base_url= "https://openrouter.ai/api/v1",
                api_key= openrouter_key,
            )
            if openai_key:
                self.fallback_client = OpenAI(api_key=openai_key)
        elif openai_key:
            self.provider = "openai"
            self.client = OpenAI(api_key=openai_key)
        else:
            raise RuntimeError("PLease add any of the 2 API keys in the .env file.")
        
        provider_default_model = "openai/gpt-4o-mini" if self.provider == "openrouter" else "gpt-4o-mini"
        self.model = model or os.getenv("MODEL") or provider_default_model
        if self.provider == "openrouter" and self.fallback_client:
            self.fallback_model = self.model.split("/", 1)[1] if "/" in self.model else self.model
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
        
        request_kwargs = {
            "model": self.model,
            "max_tokens": 2048,
            "tools": self._get_tool_schemas() if self.tools else None,
            "messages": payload,
            "temperature": 0.1,
        }
        try:
            respond = self.client.chat.completions.create(**request_kwargs)
        except APIStatusError as exc:
            if (
                self.provider == "openrouter"
                and getattr(exc, "status_code", None) == 402
                and self.fallback_client is not None
                and self.fallback_model
            ):
                fallback_kwargs = dict(request_kwargs)
                fallback_kwargs["model"] = self.fallback_model
                respond = self.fallback_client.chat.completions.create(**fallback_kwargs)
            else:
                raise
        
        # Now we save the Assistant's response/output into the short term memory
        return respond
    
        





