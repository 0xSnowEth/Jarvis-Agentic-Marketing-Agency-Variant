import os
import json
from publish_agent import publish_agent

def test_publish_agent():
    print("🤖 Starting Publish Agent (Agent #2) Tests...\n")
    
    mock_agent1_output = {
        "client_name": "client_a",
        "caption": "The new luxury villas in Dubai are now available for viewing. حياكم الله في مشاريعنا الجديدة.",
        "hashtags": ["#عقارات_دبي", "#فلل_فاخرة", "#دبي", "#استثمار_عقاري"],
        "seo_keyword_used": "عقارات دبي",
        "status": "success"
    }

    print("📝 Simulated Agent #1 Output:")
    print(json.dumps(mock_agent1_output, indent=2, ensure_ascii=False))
    print("-" * 40)
    
    result = publish_agent.publish(agent1_output=mock_agent1_output)
    
    print("\n✅ Agent #2 (Publish Agent) Results:\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("=" * 60 + "\n")

if __name__ == "__main__":
    test_publish_agent()