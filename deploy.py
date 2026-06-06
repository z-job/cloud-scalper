import os
import requests
import subprocess

PAT = "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"
headers = {"Authorization": f"token {PAT}", "Accept": "application/vnd.github.v3+json"}

print("1. Authenticating...")
res = requests.get("https://api.github.com/user", headers=headers)
if res.status_code != 200:
    print(f"Auth failed: {res.text}")
    exit(1)
username = res.json()["login"]
print(f"Authenticated as {username}")

print("2. Creating repository 'cloud-scalper'...")
repo_data = {"name": "cloud-scalper", "private": True}
res = requests.post("https://api.github.com/user/repos", headers=headers, json=repo_data)
if res.status_code not in (201, 422):
    print(f"Failed to create repo: {res.text}")
    exit(1)
print("Repository created successfully (or already exists).")

print("3. Pushing code to GitHub...")
subprocess.run(["git", "init"])
subprocess.run(["git", "branch", "-m", "main"])
subprocess.run(["git", "add", "."])
subprocess.run(["git", "commit", "-m", "Initial setup"])

remote_url = f"https://oauth2:{PAT}@github.com/{username}/cloud-scalper.git"
subprocess.run(["git", "remote", "remove", "origin"], stderr=subprocess.DEVNULL)
subprocess.run(["git", "remote", "add", "origin", remote_url])

push_res = subprocess.run(["git", "push", "-u", "origin", "main", "--force"])
if push_res.returncode == 0:
    print("SUCCESS: Code successfully pushed to GitHub!")
else:
    print("ERROR: Failed to push code.")
