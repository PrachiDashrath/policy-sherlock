import ollama

def ask_ollama(prompt: str, model: str = "qwen2.5:1.5b") -> str:
    """
    Sends a prompt to the Ollama model and returns the response.
    """
    try:
        # Define the message structure
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ]
        
        # Call the chat method
        response = ollama.chat(model=model, messages=messages)
        return response["message"]["content"]
    except Exception as e:
        return f"❌ Ollama error: {e}"
