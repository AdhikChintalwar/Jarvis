import os


def speak(text: str):
    os.system(f'say "{text}"')
