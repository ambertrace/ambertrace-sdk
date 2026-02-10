import os
import openai
import ambertrace

# 1. Initialize AmberTrace (do this once at startup)
ambertrace.init(api_key="your_ambertrace_api_key", debug=True)

my_key = os.getenv("OPENAI_API_KEY")
# 2. Use OpenAI SDK normally - tracing happens automatically!
client = openai.OpenAI(api_key=my_key)
response = client.chat.completions.create(
    model="gpt-5-nano",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
    ]
)

print(response.choices[0].message.content)

# 3. (Optional) Flush traces before exit
ambertrace.flush()