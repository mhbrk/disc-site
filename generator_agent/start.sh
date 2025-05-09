#!/bin/bash


# subscribe waits for server to start up
python subscribe_to_pubsub.py &
python ./app/main.py
