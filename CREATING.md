## Task
- Create an independent file for Ollama model to run as FAST API for request

## Step
- Create a python file name ollama_model.py
- Create a request method to receive a payload. The payload will be a key to access content of prompt for ollama
- The method will use this key to read from qdrant database
- After finish, save the ollama response to the database and send back the key so the client can read the response from it if success

## Important
- go through all the file in the python folder and replace every time we use indepedent ollama with the above method