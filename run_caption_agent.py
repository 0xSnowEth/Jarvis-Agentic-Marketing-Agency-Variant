import sys
from agents import Runner
from caption_agent import caption_agent

def run_test(client_name, topic, platform):
    request = f"Client: {client_name}\nTopic: {topic}\nPlatform: {platform}"
    print(f"📝 Request:\n{request}")
    print("-" * 40)
    sys.stdout.flush()
    
    # Run the agent synchronously
    result = Runner.run_sync(caption_agent, request)
    
    print("✅ Agent Output:\n")
    print(result.final_output)
    print("=" * 60 + "\n")
    sys.stdout.flush()

if __name__ == "__main__":
    print("🤖 Starting Caption Agent Tests...\n")
    
    # Test 1: Real estate client (Gulf Arabic)
    run_test(
        client_name="client_a",
        topic="A new line of winter coats and jackets just dropped.",
        platform="instagram"
    )
    
    # Test 2: Café client (Gulf Arabic)
    run_test(
        client_name="client_b",
        topic="Our new summer iced latte with pistachio is finally here. Perfect for the hot weather.",
        platform="facebook"
    )
    
    # Test 3: Failure handling (brand profile doesn't exist)
    run_test(
        client_name="unknown_client",
        topic="Selling cheap cars",
        platform="instagram"
    )
