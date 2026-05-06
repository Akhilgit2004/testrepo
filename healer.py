import os
import requests
import json
import subprocess

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
    
    # 1. Structured Prompting: We demand JSON output
    prompt = f"""You are an autonomous DevOps agent. Analyze this Jenkins build error.
You must respond with ONLY a valid JSON object. Do not include markdown formatting or explanations outside the JSON.

Format exactly like this:
{{
    "file_to_edit": "Jenkinsfile",
    "search_text": "text to find",
    "replace_text": "text to replace with",
    "explanation": "short reason for the change"
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
    
    # 2. Safety Check: Does the file exist and contain the text?
    if not os.path.exists(file_path):
        print(f"❌ Safety Abort: File '{file_path}' does not exist.")
        return False
        
    with open(file_path, 'r') as f:
        content = f.read()
        
    if search_text not in content:
        print(f"❌ Safety Abort: Could not find '{search_text}' in the file.")
        return False
        
    # 3. Execution: Apply the change
    content = content.replace(search_text, replace_text)
    with open(file_path, 'w') as f:
        f.write(content)
    print("✅ File modified successfully.")
    return True

def create_git_branch(explanation):
    # 4. Version Control: Create a new branch for the fix
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
    
    # AI models often wrap JSON in markdown blockticks, so we strip them out
    clean_json = raw_response.strip().removeprefix("```json").removesuffix("```").strip()
    
    try:
        # Attempt to parse the AI's response into a Python dictionary
        fix_data = json.loads(clean_json)
        print(f"🤖 AI DIAGNOSIS: {fix_data['explanation']}")
        
        # If the file edit is successful, commit it to Git
        if apply_fix(fix_data):
            create_git_branch(fix_data['explanation'])
            
    except json.JSONDecodeError:
        print("❌ AI returned invalid JSON. Cannot apply fix.")
        print(f"Raw output: {raw_response}")
        
    print("="*50 + "\n")