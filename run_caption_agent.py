import json

from caption_agent import generate_caption_payload


def run_test(client_name, topic, media_type):
    print(f"Request: client={client_name} | media_type={media_type}")
    print(f"Topic: {topic}")
    print("-" * 40)
    result = generate_caption_payload(client_name, topic, media_type)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("=" * 60 + "\n")


if __name__ == "__main__":
    print("Starting Caption Agent Tests...\n")

    run_test(
        client_name="client_a",
        topic="A new line of winter coats and jackets just dropped.",
        media_type="image_post",
    )

    run_test(
        client_name="client_b",
        topic="Our new summer iced latte with pistachio is finally here. Perfect for the hot weather.",
        media_type="image_post",
    )

    run_test(
        client_name="unknown_client",
        topic="Selling cheap cars",
        media_type="image_post",
    )
