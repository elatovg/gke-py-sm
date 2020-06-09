#!/usr/bin/env python3
import os
from flask import Flask
from google.cloud import secretmanager

# Initiate Flask framework
app = Flask(__name__)

# get the variables from the Environment Variables
project_id = os.environ.get("PROJECT_ID")
secret_name = os.environ.get("SECRET_NAME")

# Initiate the Google Secret Manager Client
secrets = secretmanager.SecretManagerServiceClient()

# get the value of the secret
secret_path = f"projects/{project_id}/secrets/{secret_name}/versions/1"
secret_text = secrets.access_secret_version(
    secret_path).payload.data.decode("utf-8")

# create a default route for Flask
@app.route("/")
def hello():
    # print the value of our secret
    return(f"the secret is {secret_text}\n")

# check if imported as a module or run as script directly
if __name__ == "__main__":
    # enable debug if desired
    # app.debug=True
    # start flask
    app.run(host="0.0.0.0", port=8000)
