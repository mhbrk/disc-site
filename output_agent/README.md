# Output Agent

Output Agent is a server that hosts the output agent in the spirit of A2A protocol (but not yet implementing it).

It is running in fastAPI web server that handles tasks from clients.

The agent is a langgraph react agent. It will take the task payload and asynchronously stream the output. The task output is then streamed to pubsub topic.

Pubsub is located at port 8000.

## Setup

Don't forget to provide your OPEN_AI_KEY in .env file.