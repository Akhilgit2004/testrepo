import os
import requests
import json
import subprocess
import re
import tempfile
import shutil

def get_latest_jenkins_log():
    """Fetches the latest Jenkins build log. Increased to 100 lines for better stack traces."""
    job_name = os.environ.get('JOB_NAME')
    build_id = os.environ.get('BUILD_ID')
    log_path = f"/var/lib/jenkins/jobs/{job_name}/builds/{build_id}/log"
    
    try:
        with open(log_path, 'r') as f:
            lines = f.readlines()
            # Grab 100 lines so the AI can see the line numbers in compiler stack traces
            return "".join(lines[-100:])
    except Exception as e:
        return f"Could not read log: {e}"

def ask_agent(error_log):
    url = "http://localhost:11434/api/generate"
    
    
    
    prompt = f"""Task: Provide a 1-line surgical fix for the error in the log.
    
    SCHEMA:
    {{
        "file_to_edit": "string",
        "line_number": "integer",
        "replace_text": "string",
        "explanation": "string"
    }}

    CRITICAL RULES:
    1. **ONE LINE ONLY**: The 'replace_text' MUST be a single line of code. Do not include the function name, braces, or surrounding context.
    2. **HEADER FIX**: If the error is "not a member of std" (like std::accumulate), the fix is to add a header. 
       - Target `line_number`: 1
       - `replace_text`: "#include <numeric>\\n#include <iostream>" (Replace line 1 with the header + the original line 1).
    3. **NO DUPLICATION**: Do not repeat any code that already exists on other lines.

    Log:
    {error_log}

    JSON Patch:"""


    payload = {
        "model": "qwen2.5-coder:7b", 
        "prompt": prompt, 
        "stream": False,
        "format": {
            "type": "object",
            "properties": {
                "file_to_edit": { "type": "string" },
                "line_number": { "type": "integer" },
                "replace_text": { "type": "string" },
                "explanation": { "type": "string" }
            },
            "required": ["file_to_edit", "line_number", "replace_text", "explanation"]
        },
        "options": {
            "temperature": 0.0,
            "stop": ["\n\n"] # Stop the model if it tries to keep talking
        }
    }
    
    response = requests.post(url, json=payload)
    return response.json().get("response")

def apply_fix_streaming(fix_data):
    """Enterprise memory-safe file modification using streams."""
    file_path = fix_data.get("file_to_edit")
    line_number = fix_data.get("line_number")
    replace_text = fix_data.get("replace_text")
    
    print(f"🛠️ Target File: {file_path} (Line {line_number})")
    
    # Safety Check 1: File Exists?
    if not os.path.exists(file_path):
        print(f"❌ Safety Abort: File '{file_path}' does not exist.")
        return False
        
    # Ensure new text has a newline so we don't break file structure
    if not replace_text.endswith('\n'):
        replace_text += '\n'

    # Create a temporary file descriptor and path
    temp_fd, temp_path = tempfile.mkstemp()
    line_replaced = False
    
    try:
        # Open temp file for writing, original file for streaming read
        with os.fdopen(temp_fd, 'w') as temp_file, open(file_path, 'r') as original_file:
            for current_index, current_line in enumerate(original_file):
                # 0-indexed check
                if current_index == (line_number - 1):
                    print(f"🔍 Swapping:\n[-] {current_line.strip()}\n[+] {replace_text.strip()}")
                    temp_file.write(replace_text)
                    line_replaced = True
                else:
                    temp_file.write(current_line)
                    
        # Safety Check 2: Did we actually find the line?
        if line_replaced:
            # Atomic swap: overwrite the original file with the temporary one
            shutil.move(temp_path, file_path)
            print("✅ Surgical streaming modification successful.")
            return True
        else:
            print(f"❌ Safety Abort: Line number {line_number} is out of bounds for this file.")
            os.remove(temp_path) 
            return False
            
    except Exception as e:
        os.remove(temp_path)
        print(f"❌ File operation failed: {e}")
        return False

def create_git_branch(explanation):
    """Creates a new Git branch, commits the fix, and pushes via secure PAT."""
    build_id = os.environ.get('BUILD_ID', 'manual')
    branch_name = f"healer-fix-build-{build_id}"
    
    try:
        subprocess.run(['git', 'checkout', '-b', branch_name], check=True, capture_output=True)
        subprocess.run(['git', 'add', '-u'], check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', f"Auto-fix: {explanation}"], check=True, capture_output=True)
        
        print("☁️ Authenticating and pushing fix to GitHub...")
        github_token = os.environ.get('GITHUB_PAT')
        
        if not github_token:
            print("❌ Push aborted: GITHUB_PAT environment variable not found in Jenkins.")
            return None
            
        auth_url = f"https://{github_token}@github.com/Akhilgit2004/testrepo.git"
        subprocess.run(['git', 'push', '--set-upstream', auth_url, branch_name], check=True, capture_output=True)
        
        print(f"🌿 Successfully pushed new branch: {branch_name}")
        return branch_name
    except subprocess.CalledProcessError as e:
        print(f"❌ Git operation failed: {e.stderr.decode()}")
        return None

if __name__ == "__main__":
    print("\n" + "="*50)
    print("🚨 HEALER AGENT: INITIATING AUTO-FIX SEQUENCE...")
    
    log_content = get_latest_jenkins_log()
    
    print("🧠 Consulting Qwen 2.5 Coder on RTX 4060...")
    raw_response = ask_agent(log_content)
    
    # DEBUG: Let's see what the AI actually said
    print(f"📡 RAW AI OUTPUT: {raw_response}")
    
    try:
        fix_data = json.loads(raw_response)

        if "response" in fix_data and isinstance(fix_data["response"], dict):
            fix_data = fix_data["response"]
        elif "response" in fix_data and isinstance(fix_data["response"], str):
             # If it gave us a string summary, we need to treat it as a failure
             print("❌ AI gave a text summary instead of a patch.")

        # SAFE DATA EXTRACTION (Preventing NoneType crashes)
        file_path = fix_data.get("file_to_edit")
        if not os.path.exists(file_path):
            print(f"⚠️ AI targeted non-existent file: {file_path}")
            # FORCE the AI to look at the log again specifically for app.cpp
            if "app.cpp" in log_content:
                 print("🔄 Redirecting AI attention to app.cpp...")
                 fix_data["file_to_edit"] = "test.cpp"
        line_num = fix_data.get("line_number")
        new_text = fix_data.get("replace_text","")
        if "int main()" in new_text and line_num > 1:
            print("⚠️ AI over-generated code. Attempting to extract only the fix...")
            # Simple heuristic: find the line with 'accumulate' or the actual fix
            for line in new_text.split('\n'):
                if "accumulate" in line or "include" in line:
                    fix_data["replace_text"] = line
                    break
        reason = fix_data.get("explanation", "No explanation provided.")

        if not all([file_path, line_num, new_text]):
            print("❌ AI returned incomplete data. Keys might be missing.")
            print(f"Keys found: {list(fix_data.keys())}")
        elif "error" in fix_data:
            print(f"🛑 AI aborted: {fix_data['error']}")
        else:
            print(f"🤖 AI DIAGNOSIS: {reason}")
            # Run the fix
            if apply_fix_streaming(fix_data):
                create_git_branch(reason)
                    
    except json.JSONDecodeError as e:
        print(f"❌ Critical JSON Error: {e}")