from openrouter import OpenRouter
import os

with OpenRouter(
    api_key=os.getenv("OPENROUTER_API_KEY", ""),
) as client:
    response = client.chat.send(
        model="google/lyria-3-pro-preview",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What is in this image?"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "https://live.staticflickr.com/3851/14825276609_098cac593d_b.jpg"
                        },
                    },
                ],
            }
        ],
    )

    print(response.choices[0].message.content)
