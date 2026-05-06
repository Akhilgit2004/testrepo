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
    """Surgical, memory-safe file modification with Smart Indentation."""
    file_path = fix_data.get("file_to_edit")
    line_number = fix_data.get("line_number")
    replace_text = fix_data.get("replace_text")
    
    if not os.path.exists(file_path):
        print(f"❌ Safety Abort: File '{file_path}' does not exist.")
        return False
        
    temp_fd, temp_path = tempfile.mkstemp()
    line_replaced = False
    
    try:
        with os.fdopen(temp_fd, 'w') as temp_file, open(file_path, 'r') as original_file:
            for current_index, current_line in enumerate(original_file):
                if current_index == (line_number - 1):
                    # 1. SPECIAL C++ HEADER CASE
                    if line_number == 1 and "#include" in replace_text:
                        print(f"🔍 Prepending Header:\n[+] {replace_text.strip()}")
                        temp_file.write(replace_text)
                        if not replace_text.endswith('\n'):
                            temp_file.write('\n')
                        temp_file.write(current_line)
                    else:
                        # 2. SMART INDENTATION MATCHING
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
        "model": "qwen2.5-coder:7b", 
        "prompt": prompt, 
        "stream": False, 
        "options": {"temperature": 0.4}
    }
    response = requests.post(url, json=payload)
    return response.json().get("response")

def get_json_patch(file_content, diagnosis):
    """STAGE 2: Focuses 100% on generating a strict JSON patch based on the file's actual code."""
    url = "http://localhost:11434/api/generate"
    prompt = f"""You are an automated code patcher. 

TARGET FILE CONTENT:{file_content}
ERROR DIAGNOSIS:
{diagnosis}

Task: Output a JSON patch to fix the file based on the diagnosis.
SCHEMA: {{"file_to_edit": "string", "line_number": integer, "replace_text": "string", "explanation": "string"}}

CRITICAL RULES:
1. Output ONLY JSON. No markdown, no text.
2. 'line_number' is the exact line to swap (1-indexed). Look at the Target File Content to count the lines.
3. 'replace_text' must be ONLY the line being changed, with no surrounding code.
4. If the fix requires adding a C++ header (like <numeric>), target line_number: 1.

JSON PATCH:"""

    payload = {
        "model": "qwen2.5-coder:7b",
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.0}
    }
    response = requests.post(url, json=payload)
    return response.json().get("response")

# ==========================================
# MAIN ORCHESTRATOR
# ==========================================

if __name__ == "__main__":
    print("\n" + "="*50)
    print("🚨 HEALER AGENT: INITIATING TWO-STAGE RECOVERY...")
    
    log_content = get_latest_jenkins_log()
    
    # ---------------------------------------------------------
    # STAGE 1: DIAGNOSIS
    # ---------------------------------------------------------
    print("\n🧠 STAGE 1: Analyzing Jenkins Log...")
    diagnosis = get_diagnosis(log_content)
    print(f"🔍 ANALYSIS: {diagnosis[:200]}...\n")
    
    # Extract the file name using regex (e.g., app.cpp, app.py)
    file_match = re.search(r'(\w+\.(cpp|py|java|js))', diagnosis)
    target_file = file_match.group(1) if file_match else "app.cpp"

    if not os.path.exists(target_file):
        print(f"⚠️ Could not find target file: {target_file}. Is the regex catching the wrong name?")
        exit(1)

    # Read the actual broken code
    with open(target_file, 'r') as f:
        current_code = f.read()
    
    # ---------------------------------------------------------
    # STAGE 2: FIX GENERATION
    # ---------------------------------------------------------
    print(f"🛠️ STAGE 2: Generating JSON patch for {target_file}...")
    raw_patch = get_json_patch(current_code, diagnosis)
    
    try:
        fix_data = json.loads(raw_patch)
        
        # Ensure we always target the correct file, even if the AI typo'd it in the JSON
        fix_data["file_to_edit"] = target_file 
        
        print(f"🤖 AI RECOMMENDS: {fix_data.get('explanation', 'Auto-fix generated.')}")
        
        # ---------------------------------------------------------
        # STAGE 3: EXECUTION
        # ---------------------------------------------------------
        if apply_fix_streaming(fix_data):
            print("✅ Code patched locally.")
            create_git_branch(fix_data.get("explanation", "Auto-fix"))
            
    except json.JSONDecodeError as e:
        print(f"❌ Critical JSON Parsing Failed: {e}")
        print(f"Raw Output was:\n{raw_patch}")
        
    print("="*50 + "\n")