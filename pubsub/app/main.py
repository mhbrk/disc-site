from contextlib import asynccontextmanager

from fastapi import FastAPI, Body
from pydantic import BaseModel

import kafka_manager


class SubscribeRequest(BaseModel):
    topic: str
    endpoint: str


class PublishRequest(BaseModel):
    topic: str
    payload: dict


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield  # App runs during this time
    kafka_manager.close()


app = FastAPI(lifespan=lifespan)


@app.post("/subscribe")
def subscribe(req: SubscribeRequest):
    kafka_manager.subscribe(req.topic, req.endpoint)
    return {"message": f"Subscribed {req.endpoint} to {req.topic}"}


@app.post("/publish")
def publish(req: PublishRequest):
    kafka_manager.publish(req.topic, req.payload)
    return {"message": f"Published to {req.topic}"}


@app.post("/echo")
def echo(payload: dict = Body(...)):
    return payload


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

"""
curl -X POST http://127.0.0.1:8000/subscribe \
  -H "Content-Type: application/json" \
  -d '{"topic": "my_topic", "endpoint": "http://localhost:8000/echo"}'

curl -X POST http://127.0.0.1:8000/publish \
  -H "Content-Type: application/json" \
  -d '{"topic": "my_topic", "payload": {"message": "hello world"}}'
"""