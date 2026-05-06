import os
import requests
import json
import subprocess
import re  # <-- NEW: Required for robust JSON extraction

def get_latest_jenkins_log():
    job_name = os.environ.get('JOB_NAME')
    build_id = os.environ.get('BUILD_ID')
    log_path = f"/var/lib/jenkins/jobs/{job_name}/builds/{build_id}/log"
    
    try:
        with open(log_path, 'r') as f:
            lines = f.readlines()
            return "".join(lines[-50:])
    except Exception as e:
        return f"Could not read log: {e}"

def ask_codegemma(error_log):
    url = "http://localhost:11434/api/generate"
    
    # UPGRADED PROMPT: Added a "One-Shot Example" and "Minimal Match" rules
    prompt = f"""You are an autonomous DevOps agent. Analyze this Jenkins build error.
You must respond with ONLY a valid JSON object.

CRITICAL RULES:
1. Focus ON THE DOCKER ERROR (e.g., 'pull access denied', 'repository does not exist').
2. Keep the `search_text` AS SHORT AS POSSIBLE. Only target the exact word or phrase that is broken (like a misspelled image name). Do not include the whole line of code.

EXAMPLE PERFECT RESPONSE:
{{
    "file_to_edit": "Jenkinsfile",
    "search_text": "typo-image",
    "replace_text": "healer-agent",
    "explanation": "The build failed because 'typo-image' does not exist. Replacing it with the correctly built 'healer-agent'."
}}

Error Log:
{error_log}
"""
    
    payload = {"model": "codegemma:7b", "prompt": prompt, "stream": False}
    response = requests.post(url, json=payload)
    return response.json().get("response")


def apply_fix(fix_data):
    file_path = fix_data.get("file_to_edit")
    search_text = fix_data.get("search_text")
    replace_text = fix_data.get("replace_text")
    
    print(f"🛠️ Target File: {file_path}")
    
    if not os.path.exists(file_path):
        print(f"❌ Safety Abort: File '{file_path}' does not exist.")
        return False
        
    with open(file_path, 'r') as f:
        content = f.read()
        
    if search_text not in content:
        print(f"❌ Safety Abort: Could not find exactly:\n'{search_text}'\n...in the file.")
        return False
        
    content = content.replace(search_text, replace_text)
    with open(file_path, 'w') as f:
        f.write(content)
    print("✅ File modified successfully.")
    return True

def create_git_branch(explanation):
    build_id = os.environ.get('BUILD_ID', 'manual')
    branch_name = f"healer-fix-build-{build_id}"
    
    try:
        subprocess.run(['git', 'checkout', '-b', branch_name], check=True, capture_output=True)
        subprocess.run(['git', 'add', '-u'], check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', f"Auto-fix: {explanation}"], check=True, capture_output=True)
        print(f"🌿 Created new branch and committed fix: {branch_name}")
        return branch_name
    except subprocess.CalledProcessError as e:
        print(f"❌ Git operation failed: {e.stderr.decode()}")
        return None

if __name__ == "__main__":
    print("\n" + "="*50)
    print("🚨 HEALER AGENT: INITIATING AUTO-FIX SEQUENCE...")
    
    log_content = get_latest_jenkins_log()
    
    print("🧠 Consulting CodeGemma on RTX 4060...")
    raw_response = ask_codegemma(log_content)
    
    # UPGRADED PARSING: Use Regex to find everything between { and }
    json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
    
    if json_match:
        clean_json = json_match.group(0)
        # SANITIZATION: Strip out the illegal backslash-escaped single quotes
        clean_json = clean_json.replace("\\'", "'")
        
        try:
            fix_data = json.loads(clean_json)
            print(f"🤖 AI DIAGNOSIS: {fix_data['explanation']}")
            
            if apply_fix(fix_data):
                create_git_branch(fix_data['explanation'])
                
        except json.JSONDecodeError as e:
            print(f"❌ JSON Parsing Failed: {e}")
            print(f"Sanitized JSON attempted: {clean_json}")
    else:
        print("❌ AI failed to return a JSON object.")
        print(f"Raw output: {raw_response}")
        
    print("="*50 + "\n")