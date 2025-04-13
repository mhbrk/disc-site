# PubSub

This is a roll-your-own implementation of Google PubSub using Kafka

## Running

### Docker Compose (Recommended)

Must have Kafka running on localhost:9092 to run. So using docker-compose.yaml is recommended from the root directory of
the project.

```bash
docker-compose up --build  
```

### Standalone docker

1. Create a custom Docker network so containers can talk to each other by name
    ```bash

    docker network create pubsub-network
    ```
2. Run the Kafka container on the shared network with a container name
    ```bash
    docker run -d \
      --name kafka \
      --network pubsub-network \
      -p 9092:9092 \
      -e KAFKA_BROKER_ID=1 \
      -e KAFKA_LISTENER_SECURITY_PROTOCOL_MAP=PLAINTEXT:PLAINTEXT \
      -e KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://kafka:9092 \
      -e KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1 \
      -e KAFKA_LOG_RETENTION_HOURS=1 \
      -e KAFKA_ZOOKEEPER_CONNECT=localhost:2181 \
      apache/kafka:4.0.0
    ```
3. Build your pubsub app Docker image
    ```bash
    docker build -t pubsub .
    ```

4. Run your pubsub container, passing the Kafka container address as an env
    ```bash
    docker run -d \
      --name pubsub \
      --network pubsub-network \
      -p 8000:8000 \
      -e KAFKA_BROKER=kafka:9092 \
      pubsub