import os

def get_openai_client():
    return os.environ.get("OPENAI_HOST")

print('OPENAI_HOST' + get_openai_client())