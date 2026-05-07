import os
import requests
import json
import subprocess
import re
import tempfile
import shutil

# ==========================================
# UTILITY FUNCTIONS
# ==========================================

def get_latest_jenkins_log():
    """Fetches the latest Jenkins build log (last 100 lines)."""
    job_name = os.environ.get('JOB_NAME')
    build_id = os.environ.get('BUILD_ID')
    log_path = f"/var/lib/jenkins/jobs/{job_name}/builds/{build_id}/log"
    
    try:
        with open(log_path, 'r') as f:
            lines = f.readlines()
            return "".join(lines[-100:])
    except Exception as e:
        return f"Could not read log: {e}"

def apply_fix_streaming(fix_data):
    """Surgical, memory-safe file modification with Smart Indentation and Universal Prepend."""
    file_path = fix_data.get("file_to_edit")
    line_number = fix_data.get("line_number")
    replace_text = fix_data.get("replace_text")
    
    if not os.path.exists(file_path):
        print(f"❌ Safety Abort: File '{file_path}' does not exist.")
        return False
        
    temp_fd, temp_path = tempfile.mkstemp()
    line_replaced = False
    
    # Define keywords that should always be prepended at the top (Line 1)
    top_level_keywords = ["#include", "import ", "from ", "package "]
    is_top_level_fix = any(k in replace_text for k in top_level_keywords)
    
    try:
        with os.fdopen(temp_fd, 'w') as temp_file, open(file_path, 'r') as original_file:
            for current_index, current_line in enumerate(original_file):
                if current_index == (line_number - 1):
                    # 1. UNIVERSAL PREPEND: For libraries/headers at Line 1, don't delete the original line!
                    if line_number == 1 and is_top_level_fix:
                        print(f"🔍 Prepending Library/Header:\n[+] {replace_text.strip()}")
                        temp_file.write(replace_text)
                        if not replace_text.endswith('\n'):
                            temp_file.write('\n')
                        temp_file.write(current_line) # Keep the original Line 1
                    else:
                        # 2. SMART INDENTATION MATCHING for standard swaps
                        # Extract the exact whitespace from the start of the original line
                        leading_spaces = current_line[:len(current_line) - len(current_line.lstrip())]
                        
                        # Strip any messy whitespace the AI tried to add
                        clean_text = replace_text.lstrip()
                        
                        print(f"🔍 Swapping:\n[-] {current_line.rstrip()}\n[+] {leading_spaces}{clean_text}")
                        
                        # Write it with perfect original indentation
                        temp_file.write(leading_spaces + clean_text + '\n')
                    line_replaced = True
                else:
                    temp_file.write(current_line)
                    
        if line_replaced:
            shutil.move(temp_path, file_path)
            return True
        else:
            print(f"❌ Safety Abort: Line {line_number} is out of bounds.")
            os.remove(temp_path)
            return False
            
    except Exception as e:
        os.remove(temp_path)
        print(f"❌ File operation failed: {e}")
        return False

def create_git_branch(explanation):
    """Commits and pushes the fix to a new branch using IPv4 to avoid GitHub API errors."""
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
        # '-4' forces IPv4, preventing the 'Bad IPv6' error you saw earlier
        subprocess.run(['git', 'push', '-4', '--set-upstream', auth_url, branch_name], check=True, capture_output=True)
        
        print(f"🌿 Successfully pushed new branch: {branch_name}")
        return branch_name
    except subprocess.CalledProcessError as e:
        print(f"❌ Git push failed: {e.stderr.decode()}")
        return None

# ==========================================
# MULTI-AGENT ARCHITECTURE
# ==========================================

def get_diagnosis(error_log):
    """STAGE 1: Focuses 100% on reasoning and identifying the root cause."""
    url = "http://localhost:11434/api/generate"
    prompt = f"""You are a Senior SRE reviewing a CI/CD pipeline failure.
Analyze the following error log. 
1. Identify the exact file that is causing the error.
2. Explain the root cause of the error.
3. State the exact code needed to fix it (e.g., missing header, syntax error).

LOG:
{error_log}

DIAGNOSIS:"""

    payload = {
        "model": "qwen3:14b", 
        "prompt": prompt, 
        "stream": False, 
        "options": {"temperature": 0.4}
    }
    response = requests.post(url, json=payload)
    return response.json().get("response")

def get_json_patch(file_content, diagnosis):
    """STAGE 2: Whole-File Repair Agent (Qwen 3.6)."""
    url = "http://localhost:11434/api/generate"
    
    prompt = f"""You are a Senior Software Engineer. 
A CI/CD pipeline failed with the following error.

ERROR LOG:
---
{diagnosis}
---

CURRENT SOURCE CODE:
---
{file_content}
---

TASK:
1. Analyze the error and the source code.
2. Create a mental plan to fix the root cause.
3. Output the ENTIRE corrected source code.

RULES:
- Provide a brief 'explanation' of the fix.
- Provide the 'fixed_code' as a complete, runnable file.
- DO NOT truncate the code. DO NOT say "// rest of code here".
- Return your answer in STRICT JSON format.

JSON RESPONSE:"""

    payload = {
        "model": "qwen3:14b",
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.2, # Low temperature for code stability
            "num_ctx": 32768    # Qwen 3.6 handles large windows easily
        }
    }
    response = requests.post(url, json=payload)
    return response.json().get("response")

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
    
    # Identify target file using regex (e.g., app.cpp, app.py)
    file_match = re.search(r'(\w+\.(cpp|py|java|js))', log_content)
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
    
    # ---------------------------------------------------------
    # STAGE 3: EXECUTION (Direct Overwrite)
    # ---------------------------------------------------------
    try:
        data = json.loads(raw_response)
        fixed_code = data.get("fixed_code")
        explanation = data.get("explanation", "Code repaired.")

        # Safety check: Ensure the AI didn't just return an empty string
        if fixed_code and len(fixed_code) > 10:
            # Overwrite the file entirely with the new 14B output
            with open(target_file, 'w') as f:
                f.write(fixed_code)
            
            print(f"✅ HEALER: {explanation}")
            print(f"✅ Successfully rewrote {target_file}.")
            create_git_branch(explanation)
        else:
            print("⚠️ Agent returned empty or truncated code. Safety abort triggered.")

    except json.JSONDecodeError as e:
        print(f"❌ Critical JSON Parsing Failed: {e}")
        print(f"Raw Output was:\n{raw_response}")
        
    print("="*50 + "\n")