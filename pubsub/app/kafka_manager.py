import asyncio
import json
import logging
import os
import threading
import time
from typing import Dict, List

import aiohttp
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import NoBrokersAvailable

logging.basicConfig(level=logging.INFO, )
logger = logging.getLogger(__name__)

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")

_topic_threads: Dict[str, threading.Thread] = {}
_subscribers: Dict[str, set[str]] = {}
_producer = None

for _ in range(10):
    try:
        _producer = KafkaProducer(
            bootstrap_servers=KAFKA_BROKER,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        break
    except NoBrokersAvailable:
        print("Kafka not available yet, retrying...")
        time.sleep(1)
else:
    raise Exception("Kafka not reachable after multiple attempts")


# TODO: provide unsubscribe mechanism
def subscribe(topic: str, endpoint: str):
    _subscribers.setdefault(topic, set()).add(endpoint)

    if topic not in _topic_threads:
        t = threading.Thread(target=_run_topic_consumer, args=(topic,), daemon=True)
        _topic_threads[topic] = t
        t.start()


def _run_topic_consumer(topic: str):
    asyncio.run(_consume_topic(topic))


def publish(topic: str, payload: dict):
    _producer.send(topic, payload)
    _producer.flush()


def close():
    _producer.close()


async def _consume_topic(topic: str):
    consumer = KafkaConsumer(
        topic,
        bootstrap_servers=KAFKA_BROKER,
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        group_id=f"group_{topic}",
        auto_offset_reset="latest"
    )

    async with aiohttp.ClientSession() as session:
        for msg in consumer:
            for endpoint in _subscribers.get(topic, []):
                logger.debug(f"Pushing message to {endpoint} for topic {topic}: {msg.value}")
                await _post(session, endpoint, msg.value)


async def _post(session: aiohttp.ClientSession, endpoint: str, data: dict):
    try:
        async with session.post(endpoint, json=data, timeout=30) as resp:
            text = await resp.text()
            logger.info(f"Posted to {endpoint}: {resp.status} - {text}\n {data}")
    except aiohttp.ClientError as e:
        logger.error(f"[aiohttp.ClientError] Failed posting to {endpoint}: {e}")
    except Exception as e:
        logger.exception(f"[General Exception] Failed posting to {endpoint}: {e}")
