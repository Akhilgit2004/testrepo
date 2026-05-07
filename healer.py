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

def get_fixed_code(file_content, error_log,attempt=1):
    """Uses the 14B model to think and rewrite the entire file in a Markdown block."""
    url = "http://localhost:11434/api/generate"
    
    # NEW: If it's a retry, aggressively tell the AI it failed!
    retry_context = ""
    if attempt > 1:
        retry_context = "\nCRITICAL: Your previous fix FAILED to compile. Please read the NEW error log below and try again."

    prompt = f"""You are a Senior Software Engineer. {retry_context}

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
- DO NOT truncate the code. You MUST output the entire file.
- The code must be inside triple backticks (```cpp ... ```).

RESPONSE:"""

    payload = {
        "model": "qwen3:14b", 
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,  # Lowered to 0.1 for strict syntax logic
            "num_predict": 4096, # Give it enough room for the file, but prevents endless loops
            "num_ctx": 16384
        }
    }
    
    response = requests.post(url, json=payload)
    return response.json().get("response", "")
    
def verify_fix(target_file):
    """Attempts to compile the code locally. Returns (Success_Boolean, Error_String)."""
    # Adjust this command if you are testing Python (e.g., 'python3 -m py_compile')
    compile_cmd = ['g++', target_file, '-o', 'test_build']
    cmd_str = " ".join(compile_cmd)
    print(f"🧪 VERIFICATION: Running '{cmd_str}'...")
    result = subprocess.run(compile_cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        return True, ""
    else:
        # Return the new compiler error so the AI can read it
        return False, result.stderr

# ==========================================
# MAIN ORCHESTRATOR
# ==========================================

if __name__ == "__main__":
    print("\n" + "="*50)
    print("🚨 HEALER AGENT: INITIATING SELF-HEALING LOOP...")
    
    # 1. Get the initial failing log from Jenkins
    print("🧠 STAGE 1: Reading Jenkins logs...")
    log_content = get_latest_jenkins_log()
    
    # 2. Identify target file using regex (e.g., app.cpp, app.py)
    file_match = re.search(r'(\w+\.(cpp|py|java|js))', str(log_content))
    target_file = file_match.group(1) if file_match else "app.cpp"

    if not os.path.exists(target_file):
        print(f"⚠️ Could not find target file: {target_file}. Aborting.")
        exit(1)

    MAX_RETRIES = 2
    
    # 3. The Self-Healing Loop
    for attempt in range(1, MAX_RETRIES + 1):
        print(f"\n🔄 ATTEMPT {attempt}/{MAX_RETRIES}...")
        
        # Read the current state of the code
        with open(target_file, 'r') as f:
            current_code = f.read()

        # Ask AI for the fix
        print(f"🛠️ Generating fix (this may take a few minutes)...")
        raw_response = get_fixed_code(current_code, log_content, attempt)
        
        # Extract the code block safely using regex
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