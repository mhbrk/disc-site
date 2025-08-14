import asyncio

from dotenv import load_dotenv
from openai import OpenAI, AsyncOpenAI

from breba_app.generator_agent.instruction_reader import get_instructions

load_dotenv()

client = AsyncOpenAI()


html = """<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Hello World</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        html, body {
            height: 100%;
            margin: 0;
            padding: 0;
            width: 100vw;
            min-height: 100vh;
        }

        body {
            min-height: 100vh;
            min-width: 100vw;
            display: flex;
            align-items: center;
            justify-content: center;
            background: url('https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=1500&q=80') no-repeat center center fixed;
            background-size: cover;
            position: relative;
        }

        .overlay {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(255, 255, 255, 0.65);
            backdrop-filter: blur(2px);
            z-index: 1;
        }

        .center-message {
            position: relative;
            z-index: 2;
            font-size: 2rem;
            font-weight: 400;
            letter-spacing: 0.01em;
            text-align: center;
            color: #111;
            background: rgba(255, 255, 255, 0.85);
            border-radius: 0.5em;
            padding: 1.2em 2em;
            box-shadow: 0 2px 16px 0 rgba(0, 0, 0, 0.07);
        }

        @media (max-width: 600px) {
            .center-message {
                font-size: 1.2rem;
                padding: 1em 1em;
            }
        }
    </style>
</head>
<body>
<div class="overlay" aria-hidden="true"></div>
<div class="center-message">
    Hello World
</div>

<div class="center-message">
    Hello World2
</div>

</body>
</html>
"""


SYSTEM_PROMPT = get_instructions("generator_diffing_prompt")


async def diff_stream(html: str, prompt: str):
    print("Generating diff")
    stream = await client.responses.create(
        model="gpt-4.1",
        temperature=0,
        instructions=SYSTEM_PROMPT,
        stream=True,
        input=[
            {
                "role": "user",
                "content": f"#Given the following HTML:\n{html}\n\n"
                           f"##User Request:\n{prompt}"
            },
        ],
    )

    async for event in stream:
        if event.type == "response.output_text.delta":
            yield event.delta


# response = client.responses.create(
#     model="gpt-4.1",
#     temperature=0,
#     instructions=main_system,
#     input=[
#         {
#             "role": "user", "content": f"{html}\n\nThe user has highlighted the following text on the generated page: Hello. \nAnd made the following comment: Make this smaller"
#         },
#     ],
# )


# response = client.responses.create(
#     model="gpt-4.1-mini",
#     temperature=0,
#     instructions=main_system,
#     input=[
#         {
#             "role": "user", "content": f"{html}\n\nThe user has highlighted the following text on the generated page: Hello World. \nAnd made the following comment: Should be Hello, Universe!"
#         },
#     ],
# )
