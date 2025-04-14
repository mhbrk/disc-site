import httpx

PUBSUB_URL: str = "http://127.0.0.1:8000"
PUSH_ENDPOINT: str = "http://my-localhost:7999/echo"
OUTPUT_AGENT_TOPIC: str = "output_agent_topic"

url = f"{PUBSUB_URL}/subscribe"
payload = {
    "topic": OUTPUT_AGENT_TOPIC,
    "endpoint": PUSH_ENDPOINT
}

headers = {"Content-Type": "application/json"}

response = httpx.post(url, json=payload, headers=headers)

print(response.status_code)
print(response.json())
