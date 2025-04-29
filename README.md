# disc-site

DisC stands for Documentation is Code. It is a concept where an AI agent reads natural language instructions 
and executes them similar to how an interpreter executes python code instructions.

`disc-site` is a DisC solution for generating highly personalized websites.

## The Problem

The internet has deviated from its original promise of providing information that you need on demand and here are some reasons why:
* Ad driven platforms are using opaque algorithms to guide your discovery of information
* Attention harvesting platforms create distractions instead of focusing on what you need
* Algorithms impede discovery of internet resource by giving you a siloed experience

All of that makes users exposed to suboptimal, impersonal, and in some cases harmful presentations of internet resources. For example:
* For people who love outdoors, weather websites require many interactions to find the right information resulting in wasted time.
* News aggregators try to feed you clickbait, misinformation, and targeted content.
* Social media platforms have focused on attention harvesting instead of facilitating meaningful interactions with your friends and communities.
* And for all of the above, popups and ads litter the screen obscuring content useful to you.
* Flashy ads are purposefully trying to get clicks from kids
* Countless other examples exist

## The Solution
What if you could build software by typing up the requirements without writing any code? What if you could build your own website that contains all the information you need without ads and distractions?


With the advent of useful LLMs and using Event Driven Agentic Architectures, `disc-site` will allow every human to build their own sites by simply typing in their own native language.  

## Implementation
### User Interface
![User interface](images/UI.png)
* For this hack, I was able to implement the Chat, Builder, Generator, and Status panels.
* The user communicates with Builder using the chat, then the builder sends tasks to the Generator, then the generator builds the HTML and streams to the `iframe` on the front end.
* Status subscribes to all the agent topics and tries to provide some insights into what is going on in the background.
* The user can also directly edit the spec created by the builder and send it to the generator
* Highlighting elements inside the generated site allows to provide inline requests to the builder
* Interactive sites can be generated and post requests from those go the Act Agent who can execute them

### Agent Architecture
![Agent Architecture](images/architecture.png)

* At the core of the architecture is the PubSub implementation with Kafka message broker for communication. (See [PubSub Architecture](#Event-Driven-Architecture-using-Publisher-Subscriber-Pattern))
* WebApp, Chat Agent (a pseudo agent for now), Builder Agent, and Generator Agent communicate using PubSub and kafka topics.(See [Communication Scheme](#Communication-Scheme))

### Builder Agent
* The Builder Agent is a server that hosts the agent in the spirit of A2A protocol. Although currently only supports SendTaskRequests and SendTaskResponses without streaming. 

* The Builder Agent's job is to help craft a well written spec for the Generator Agent. It knows about the Generator Agent's capabilities and best practices for writing requirements for the Generator Agent.


#### Basic Operational Flow
1. It handles incoming tasks by subscribing to the pubsub topic
2. It then publishes responses to its own pubsub topic
3. In the future, it will be streaming by turning into a plan and execute agent streaming each execution step.

The agent is a langgraph custom agent that looks like this:
```mermaid
flowchart TD
    start([__start__])
    agent([agent])
    extract_prompt([extract_prompt])
    get_user_input([get_user_input])
    end_state([__end__])

    start --> agent
    agent -. final .-> extract_prompt
    extract_prompt --> end_state
    agent -. ask human .-> get_user_input
    get_user_input --> agent

```

For more information see [Builder Agent README.md](builder_agent/README.md)

### Generator Agent
* The Generator Agent is a server that hosts the agent in the spirit of A2A protocol. Although currently only supports SendTaskRequests and SendTaskResponses $with$ streaming.
* It subscribes to a pub sub topic to receive detailed description of a website to be generated.
* It uses DALL-E model deployed on Azure AI Foundry for image generation.
* It uses Tavily Web Search to look up information.

#### Basic Operational Flow
1. Generator Agent subscribes to pubsub topic where description of a website gets published.
2. It reasons about the prompt and may decide to look up information using Tavily Web Search.
3. It may decide to generate a number of image using DALL-E 3 model 
4. The image generation tool returns file name, but the image is generated in the background.
5. Once the agent has data and image names, it will start generating html.
6. Task Manager will stream individual html tags to a PubSub topic.
7. When an image is completed, the Image Generator tool will publish a COMPLETED task for that image to the same PubSub topic

```mermaid
sequenceDiagram
    participant PubSub
    participant TaskManager
    participant GeneratorAgent
    participant TavilySearch
    participant ImageGenerator
    participant DALL_E_3

    PubSub->>TaskManager: Publish Website Description
    TaskManager->>GeneratorAgent: passes Website Description
    GeneratorAgent->>GeneratorAgent: Reason about prompt
    alt Needs more info
        GeneratorAgent->>TavilySearch: Perform Web Search
        TavilySearch-->>GeneratorAgent: Return external data
    end
    alt Needs images
        GeneratorAgent->>ImageGenerator: Request Image Generation
        ImageGenerator-->>GeneratorAgent: Return image file name
    alt asynchronous task
        ImageGenerator->>DALL_E_3: async generate_image(prompt)
        DALL_E_3-->>ImageGenerator: return image_url
        ImageGenerator-->>PubSub: Publish COMPLETED task for image
    end
    end
    GeneratorAgent->>TaskManager: stream agent output
    TaskManager->>PubSub: Stream individual HTML tags
```
For more information see [Generator Agent README.md](generator_agent/README.md)

### Chat Pseudo agent
Chat agent is a server that hosts ChainLit app. 
- It is currently not a real agent, but it is intended to be one in the future in order to handle complex features.
- It is an A2A Client that sends TaskRequests to PubSub topic for the Builder Agent
- It receives responses from the app via `on_window_message` event passed by the WebApp through an iframe.


#### Basic Operational Flow
1. The user types a message to start interaction.
2. ChainLit `on_message` event handler generates a task request and sends it to the pubsub topic
3. The Builder Agent listens to that topic and picks up the task request
4. The Builder Agent generates a task response and sends it back to its own pubsub topic
5. WebApp uses WebSocket to pass the task response back to the front end
6. Front end posts message to the iframe
7. ChainLit `on_window_message` event handler picks up the response and shows it to the user


```mermaid
sequenceDiagram
    participant User
    participant ChainLit
    participant FrontEnd
    participant PubSub
    participant BuilderAgent
    participant WebApp

    User->>ChainLit: Type message
    ChainLit->>PubSub: Publish task request (on_message)
    PubSub->>BuilderAgent: Deliver task request
    BuilderAgent->>PubSub: Publish task response
    PubSub->>WebApp: Deliver task response
    WebApp->>FrontEnd: Send task response via WebSocket
    FrontEnd->>ChainLit: Deliver response (on_window_message)
    ChainLit->>User: Show response
```
For more information see [Chat Agent README.md](chat_agent/README.md)

### Act Agent
- Act Agent is a standalone agent implement using Azure AI Foundry and is accessed via a WebApp endpoint. 
- One benefit of turning it into an A2A is to allow communication with the Generator Agent to learn how the Act Agent can support the Generator Agent.

- Its purpose is to support interactivity for a generated webpage. Since the tasks could be of any kind we need an agent,
not just any endpoint. In fact, it is basically an MCP server that could in theory support any kind of tool. A higher order MCP server?
A dynamic MCP server?

- For example, right now it supports storing data in a file to handle form submissions, but in the future, it could send
an email, write a GitHub issue comment, write to a DB, and any other thing that you can find an MCP server for.

#### Basic Operational Flow

1. Takes a prompt
2. Determines which tool is needed
3. Calls tool
4. Sends back feedback

```mermaid
flowchart TD
    start([__start__])
    agent([agent])
    tools([tools])
    end_state([__end__])
    start --> agent
    agent -.-> end_state
    agent -.-> tools
    tools --> agent
```
For more information see [Act Agent README.md](act_agent/README.md)

### Event Driven Architecture using Publisher-Subscriber Pattern
![PubSub](images/pubsub.png)
- This diagram shows the full cycle of communication between the agents and the browser and highlights how session id is passed between them.
- PubSub is my own implementation of Google PubSub using Kafka for message queuing

#### Basic Operational Flow

0. WebApp and agent subscribe to various topics
1. Browser establishes session for its websocket connection
2. After some interactions, WebApp publishes a task request tagging it with session id (task_id too, but not shown here)
3. PubSub pushes the task request to the agent3.1 
4. After using session_id to get state from memory store and performing its task, the Agent publishes a task response tagged with session_id(and task_id)
5. PubSub pushes the task response to the WebApp
6. WebApp pushes the task response to the browser 

For more information see [PubSub README.md](pubsub/README.md)
### Communication Scheme
![Communication Scheme](images/communication.png)
- This diagram maps out the topics and their roles.
- WebApp subscribes to all topics in order to provide status updates to the user

## Demo
View a quick demo here:
https://youtu.be/9UjL_a_ux_E


