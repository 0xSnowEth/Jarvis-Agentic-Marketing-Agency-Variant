from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()


class Agent:
    """A Simple AI Agent that can answer questions"""

    def __init__(self):
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")

        if openrouter_key:
            self.client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=openrouter_key,
            )
        elif openai_key:
            self.client = OpenAI(api_key=openai_key)
        else:
            raise RuntimeError("Set OPENROUTER_API_KEY or OPENAI_API_KEY in .env")

        # prefer a stable, unguarded model where available
        self.model = os.getenv("MODEL", "gpt-4o-mini")
        self.system_message = (
            "You are a helpful assistant that can help break down problems into steps and solve them systematically"
        )
        self.messages = []

    def chat(self, message):
        """Process a user message and return a response"""
        
        # Store user input in short term memory
        self.messages.append({"role": "user", "content": message})
        payload = [{"role": "system", "content": self.system_message}] + self.messages

        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=1024,
            messages= payload,
            temperature=0.1,
        )
        
        # Store assistant's response in short term memory 
        assistant_text = response.choices[0].message.content
        self.messages.append({"role": "assistant", "content": assistant_text})
        return assistant_text
        
agent = Agent()
print(agent.chat("I have 4 apples, How many do you have?"))
print(agent.chat("I ate 1 apple. How many are left?"))