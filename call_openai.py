"""
Script to call OpenAI GPT model with a custom prompt.
"""
from openai import OpenAI
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def call_openai_gpt(prompt: str, api_key: str, model: str = "gpt-4o-mini") -> str:
    """
    Call OpenAI GPT model with a prompt.

    Args:
        prompt: The prompt to send to the model
        api_key: OpenAI API key
        model: Model to use (default: gpt-4o-mini)

    Returns:
        The model's response
    """
    client = OpenAI(api_key=api_key)

    print(f"Calling OpenAI {model}...")

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    return response.choices[0].message.content


if __name__ == "__main__":
    # Get API key from environment variable or set it directly here
    api_key = os.environ.get("OPENAI_API_KEY")

    if not api_key:
        # Option 1: Set your API key directly here (not recommended for production)
        # api_key = "sk-proj-..."  # Replace with your actual API key

        # Option 2: Exit if no key found
        print("Error: OPENAI_API_KEY not set")
        print("\nTo set your API key:")
        print("1. Environment variable: export OPENAI_API_KEY='your-key-here'")
        print("2. Create .env file with: OPENAI_API_KEY=your-key-here")
        print("3. Or uncomment line above and paste your key directly")
        exit(1)

    # Your prompt here
    prompt = """
    Write your prompt here.
    """

    # Call the model
    response = call_openai_gpt(prompt, api_key)

    # Print the response
    print("\n" + "="*50)
    print("Response:")
    print("="*50)
    print(response)
