import ollama

response = ollama.chat(model="qwen2.5:1.5b", messages=[
    {"role": "user", "content": "Hello Ollama! Explain yourself in 2 lines."}
])

print(response['message']['content'])
