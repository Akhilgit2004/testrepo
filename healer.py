import os
import requests
import subprocess
import re

# ==========================================
# UTILITY FUNCTIONS
# ==========================================

def get_latest_jenkins_log():
    """Fetches the latest Jenkins build log (last 100 lines)."""
    job_name = os.environ.get('JOB_NAME', 'unknown_job')
    build_id = os.environ.get('BUILD_ID', 'unknown_build')
    log_path = f"/var/lib/jenkins/jobs/{job_name}/builds/{build_id}/log"
    
    try:
        with open(log_path, 'r') as f:
            lines = f.readlines()
            return "".join(lines[-100:])
    except Exception as e:
        return f"Could not read log: {e}"

def create_git_branch(explanation):
    """Commits and pushes the fix to a new branch using IPv4."""
    build_id = os.environ.get('BUILD_ID', 'manual')
    branch_name = f"healer-fix-build-{build_id}"
    token = os.environ.get('GITHUB_PAT', '').strip()
    
    if not token:
        print("❌ Push aborted: GITHUB_PAT environment variable not found.")
        return None
        
    auth_url = f"https://{token}@github.com/Akhilgit2004/testrepo.git"
    
    try:
        subprocess.run(['git', 'checkout', '-b', branch_name], check=True, capture_output=True)
        subprocess.run(['git', 'add', '-u'], check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', f"Auto-fix: {explanation}"], check=True, capture_output=True)
        
        print("☁️ Authenticating and pushing fix to GitHub...")
        subprocess.run(['git', 'push', '-4', '--set-upstream', auth_url, branch_name], check=True, capture_output=True)
        
        print(f"🌿 Successfully pushed new branch: {branch_name}")
        return branch_name
    except subprocess.CalledProcessError as e:
        print(f"❌ Git push failed: {e.stderr.decode()}")
        return None

# ==========================================
# STAGE 2: WHOLE-FILE REPAIR AGENT
# ==========================================

def get_fixed_code(file_content, error_log):
    """Uses the 14B model to think and rewrite the entire file in a Markdown block."""
    url = "http://localhost:11434/api/generate"
    
    prompt = f"""You are a Senior Software Engineer. 
A CI/CD pipeline failed with the following error.

ERROR LOG:
---
{error_log}
---

CURRENT SOURCE CODE:
---
{file_content}
---

TASK:
1. Analyze the error and identify ALL bugs in the code.
2. Rewrite the entire file to fix the root causes.
3. Output the ENTIRE corrected source code inside a single Markdown code block.

RULES:
- Provide a brief explanation before the code block.
- DO NOT truncate the code. You MUST output the entire file.
- The code must be inside triple backticks (```cpp ... ```).

RESPONSE:"""

    payload = {
        # Change this to "qwen3:14b" if you pulled the Qwen 3 version!
        "model": "qwen2.5-coder:14b", 
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_ctx": 32768,
            "num_predict": 8192 # Crucial: Allows the model to write 150+ lines
        }
    }
    
    try:
        response = requests.post(url, json=payload)
        return response.json().get("response", "")
    except Exception as e:
        print(f"❌ API Request Failed: {e}")
        return ""

# ==========================================
# MAIN ORCHESTRATOR
# ==========================================

if __name__ == "__main__":
    print("\n" + "="*50)
    print("🚨 HEALER AGENT: INITIATING WHOLE-FILE RECOVERY...")
    
    # ---------------------------------------------------------
    # STAGE 1: LOG INGESTION
    # ---------------------------------------------------------
    print("🧠 STAGE 1: Reading Jenkins logs...")
    log_content = get_latest_jenkins_log()
    
    # Identify target file using regex
    file_match = re.search(r'(\w+\.(cpp|py|java|js))', str(log_content))
    target_file = file_match.group(1) if file_match else "app.cpp"

    if not os.path.exists(target_file):
        print(f"⚠️ Could not find target file: {target_file}. Aborting.")
        exit(1)

    with open(target_file, 'r') as f:
        current_code = f.read()

    # ---------------------------------------------------------
    # STAGE 2: WHOLE-FILE GENERATION (14B Engine)
    # ---------------------------------------------------------
    print(f"🛠️ STAGE 2: Generating complete, corrected file for {target_file}...")
    raw_response = get_fixed_code(current_code, log_content)
    
    if not raw_response:
        print("❌ Critical Failure: Received empty response from Ollama API.")
        exit(1)
    
    # ---------------------------------------------------------
    # STAGE 3: EXECUTION (Markdown Extraction)
    # ---------------------------------------------------------
    print("⚙️ Parsing Markdown output...")
    
    # Extract everything between ``` language and ```
    match = re.search(r'```[a-zA-Z]*\n(.*?)```', str(raw_response), re.DOTALL)
    
    if match:
        fixed_code = match.group(1).strip()
        
        # Safety check: Ensure the AI wrote a substantial file
        if len(fixed_code) > 100: 
            with open(target_file, 'w') as f:
                f.write(fixed_code)
            
            print(f"✅ HEALER: Extracted {len(fixed_code.splitlines())} lines of code.")
            print(f"✅ Successfully rewrote {target_file}.")
            create_git_branch("Agent applied multi-bug whole-file fix")
        else:
            print("⚠️ Extracted code was too short (might be truncated). Safety abort.")
            print(f"Snippet extracted: \n{fixed_code[:200]}")
            
    else:
        print("❌ Critical Failure: Could not find a Markdown code block in the AI's response.")
        print("Raw Response snippet (First 1000 chars):")
        print(str(raw_response)[:1000])
        
    print("="*50 + "\n")