from openai import OpenAI
import os
from dotenv import load_dotenv


def qwen_query(
    messages,
    model="qwen3-235b-a22b",
    temperature=0.7,
    top_p=0.9,
    max_tokens=16384,
    stream=False,
    enable_thinking=True,
    stop=None,
    presence_penalty=0.0,
    frequency_penalty=0.0,
):
    load_dotenv()
    client = OpenAI(
        api_key=os.getenv("ALI_DASHSCOPE_API_KEY"),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )

    extra_body = {
        "enable_thinking": enable_thinking
    }

    if stop is not None:
        extra_body["stop"] = stop

    completion = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        stream=stream,
        presence_penalty=presence_penalty,
        frequency_penalty=frequency_penalty,
        extra_body=extra_body
    )

    return completion

if __name__ == "__main__":
    messages = [
        {"role": "system", "content": "你是一个有推理能力的助手。"},
        {"role": "user", "content": "请逐步思考并回答：1+2+3+...+100 等于多少？"}
    ]

    response = qwen_query(messages, stream=True, enable_thinking=True)

    for chunk in response:
        print(chunk.choices[0].delta.content or "", end="", flush=True)