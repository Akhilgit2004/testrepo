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
    """Dynamically builds a Few-Shot prompt and queries the local Ollama model."""
    url = "http://localhost:11434/api/generate"
    
    # 1. DYNAMIC CONTEXT
    error_lower = error_log.lower()
    if "docker" in error_lower or "pull access" in error_lower:
        context_hint = "This is a Docker/Infrastructure failure. Focus on image names, tags, and Dockerfile syntax."
    elif "javac" in error_lower or "maven" in error_lower:
        context_hint = "This is a Java build failure. Focus on standard Java syntax, missing semicolons, or undefined variables."
    elif "gcc" in error_lower or "g++" in error_lower or "make" in error_lower:
        context_hint = "This is a C/C++ compilation error. Focus on syntax, pointers, and memory leaks."
    elif "python" in error_lower or "traceback" in error_lower:
        context_hint = "This is a Python runtime error. Focus on indentation, missing imports, and logic bugs."
    else:
        context_hint = "This is a general CI/CD pipeline failure. Find the core error and fix it."

    # 2. SYSTEM ROLE & CONSTRAINTS
    prompt = f"""You are 'Healer', an elite, autonomous Site Reliability Engineer (SRE).
Your sole purpose is to read failed CI/CD logs, identify the root cause, and output a JSON patch to fix the code.

CONTEXT:
{context_hint}

CRITICAL RULES:
1. OUTPUT ONLY JSON. No introductory text, no markdown formatting (do not use ```json).
2. `line_number` MUST BE AN INTEGER representing the exact line where the error occurred (1-indexed). Look for file paths and line numbers in the stack trace.
3. `replace_text` must contain the FULL, corrected line of code.
4. NO ESCAPED SINGLE QUOTES. Do not use \\' inside your JSON strings. Use standard single quotes.
5. If you cannot confidently fix the error, or the error is too complex, output EXACTLY: {{"error": "Manual intervention required"}}
6. You MUST include an "explanation" key briefly describing the fix.

EXAMPLE 1 (Docker Infrastructure):
{{
    "file_to_edit": "Jenkinsfile",
    "line_number": 14,
    "replace_text": "sh 'docker run --rm healer-agent:latest'",
    "explanation": "Corrected misspelled Docker image."
}}

EXAMPLE 2 (Python Syntax Error):
{{
    "file_to_edit": "src/main.py",
    "line_number": 42,
    "replace_text": "    print('Hello world')",
    "explanation": "Added missing closing parenthesis."
}}

EXAMPLE 3 (C++ Compilation Error):
{{
    "file_to_edit": "src/app.cpp",
    "line_number": 105,
    "replace_text": "int count = 0;",
    "explanation": "Added missing semicolon."
}}

ANALYZE THIS LOG AND GENERATE THE JSON FIX:
{error_log}
"""
    
    # 3. EXECUTION (Temperature 0.1 for strict, deterministic JSON generation)
    payload = {
        "model": "qwen2.5-coder:7b", 
        "prompt": prompt, 
        "stream": False,
        "format": "json",         
        "options": {"temperature": 0.0}
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
            
        auth_url = f"https://{github_token}@[github.com/Akhilgit2004/testrepo.git](https://github.com/Akhilgit2004/testrepo.git)"
        subprocess.run(['git', 'push', '--set-upstream', auth_url, branch_name], check=True, capture_output=True)
        
        print(f"🌿 Successfully pushed new branch: {branch_name}")
        return branch_name
    except subprocess.CalledProcessError as e:
        print(f"❌ Git operation failed: {e.stderr.decode()}")
        return None

if __name__ == "__main__":
    print("\n" + "="*50)
    print("HEALER AGENT: INITIATING AUTO-FIX SEQUENCE")
    
    log_content = get_latest_jenkins_log()
    
    print("Consulting Agent")
    raw_response = ask_agent(log_content)
    
    # Robust Regex Extraction
    json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
    
    if json_match:
        clean_json = json_match.group(0).replace("\\'", "'")
        
        try:
            fix_data = json.loads(clean_json)
            
            # Bail-out condition check
            if "error" in fix_data:
                print(f"🛑 AI aborted fix: {fix_data['error']}")
            else:
                print(f"🤖 AI DIAGNOSIS: {fix_data['explanation']}")
                
                # Execute the streaming fix and Git push
                if apply_fix_streaming(fix_data):
                    create_git_branch(fix_data['explanation'])
                    
        except json.JSONDecodeError as e:
            print(f"❌ JSON Parsing Failed: {e}")
            print(f"Sanitized JSON attempted:\n{clean_json}")
    else:
        print("❌ AI failed to return a JSON object.")
        print(f"Raw output:\n{raw_response}")
        
    print("="*50 + "\n")