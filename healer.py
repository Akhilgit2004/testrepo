import os
import requests
import subprocess
import re

# ==========================================
# CONFIGURATION
# ==========================================
MODEL = "qwen3:14b"
MAX_RETRIES = 2

# ==========================================
# UTILITY FUNCTIONS
# ==========================================

def get_latest_jenkins_log():
    """Fetches the latest Jenkins build log."""
    job_name = os.environ.get('JOB_NAME', 'unknown_job')
    build_id = os.environ.get('BUILD_ID', 'unknown_build')
    log_path = f"/var/lib/jenkins/jobs/{job_name}/builds/{build_id}/log"
    
    try:
        with open(log_path, 'r') as f:
            lines = f.readlines()
            return "".join(lines[-100:])
    except Exception as e:
        return f"Could not read log: {e}"

def verify_fix(target_file):
    """Dynamically detects the build system and verifies the code."""
    print(f"🔍 VERIFICATION: Analyzing repository to detect build system...")
    
    compile_cmd = []
    
    # 1. Check for Make (C/C++)
    if os.path.exists("Makefile"):
        print("🛠️ Build System Detected: Make")
        compile_cmd = ['make']
        
    # 2. Check for Node.js
    elif os.path.exists("package.json"):
        print("🛠️ Build System Detected: npm")
        compile_cmd = ['npm', 'run', 'build']
        
    # 3. Check for Maven (Java)
    elif os.path.exists("pom.xml"):
        print("🛠️ Build System Detected: Maven (Java)")
        compile_cmd = ['mvn', 'clean', 'compile']
        
    # 4. Check for Gradle (Java)
    elif os.path.exists("build.gradle") or os.path.exists("build.gradle.kts"):
        print("🛠️ Build System Detected: Gradle (Java)")
        # Use local gradlew wrapper if it exists, otherwise use system gradle
        if os.path.exists("gradlew"):
            compile_cmd = ['./gradlew', 'build']
        else:
            compile_cmd = ['gradle', 'build']
        
    # 5. Check for Python (Syntax Check only)
    elif target_file.endswith(".py"):
        print("🛠️ Build System Detected: Python (Syntax Check)")
        compile_cmd = ['python3', '-m', 'py_compile', target_file]
        
    # 6. Fallback for standalone Java files
    elif target_file.endswith(".java"):
        print("🛠️ Build System Detected: Standalone Java")
        compile_cmd = ['javac', target_file]
        
    # 7. Fallback for standalone C/C++ files
    elif target_file.endswith(".cpp") or target_file.endswith(".c"):
        print("🛠️ Build System Detected: Standalone C/C++")
        compile_cmd = ['g++', target_file, '-o', 'test_build']
        
    # 8. Unknown Environment
    else:
        print("⚠️ No standard build system detected. Assuming code is valid.")
        return True, ""

    # Execute the dynamically chosen command
    cmd_str = " ".join(compile_cmd)
    print(f"🧪 VERIFICATION: Running '{cmd_str}'...")
    
    result = subprocess.run(compile_cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        return True, ""
    else:
        return False, result.stderr

def create_git_branch(explanation):
    """Commits and pushes the fix to a new branch."""
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
# STAGE 2: MULTI-FILE REPAIR ENGINE
# ==========================================

def gather_context(main_file_content):
    """Scans for local includes and extracts their content for AI context."""
    context_str = ""
    
    # Regex to find C++ local includes, e.g., #include "utils.h"
    # (Ignores system includes like <iostream>)
    local_includes = re.findall(r'#include\s+"([^"]+)"', main_file_content)
    
    for file_name in local_includes:
        if os.path.exists(file_name):
            print(f"📚 CONTEXT: Injecting {file_name} into AI memory...")
            with open(file_name, 'r') as f:
                context_str += f"\n--- SUPPORTING FILE: {file_name} ---\n{f.read()}\n"
        else:
            print(f"⚠️ CONTEXT: Could not find {file_name} locally.")
            
    return context_str

def get_fixed_code(file_content, error_log, supporting_context, attempt=1):
    """Uses the LLM to rewrite the entire file with multi-file context."""
    url = "http://localhost:11434/api/generate"
    
    retry_context = ""
    if attempt > 1:
        retry_context = "\nCRITICAL: Your previous fix FAILED to compile. Please read the NEW error log below and try again."

    prompt = f"""You are a Senior Software Engineer. {retry_context}

ERROR LOG:
---
{error_log}
---

CURRENT SOURCE CODE (Needs Fixing):
---
{file_content}
---
{supporting_context}

TASK:
1. Identify and fix ALL bugs in the CURRENT SOURCE CODE.
2. Ensure logic aligns with any provided SUPPORTING FILES.
3. Output the ENTIRE corrected CURRENT SOURCE CODE inside a single Markdown block.

RULES:
- DO NOT rewrite the supporting files. Only fix the main source code.
- DO NOT truncate the code. You MUST output the entire file.
- Use triple backticks (```cpp ... ```).

RESPONSE:"""

    payload = {
        "model": MODEL, 
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 4096,
            "num_ctx": 24576 # Increased to ensure large contexts fit easily
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
    print("🚨 HEALER AGENT: INITIATING MULTI-FILE RECOVERY...")
    
    log_content = get_latest_jenkins_log()
    
    file_match = re.search(r'(\w+\.(cpp|py|java|js))', str(log_content))
    target_file = file_match.group(1) if file_match else "app.cpp"

    if not os.path.exists(target_file):
        print(f"⚠️ Could not find target file: {target_file}. Aborting.")
        exit(1)

    for attempt in range(1, MAX_RETRIES + 1):
        print(f"\n🔄 ATTEMPT {attempt}/{MAX_RETRIES}...")
        
        with open(target_file, 'r') as f:
            current_code = f.read()

        # Gather supporting files before talking to the LLM
        supporting_context = gather_context(current_code)

        print(f"🛠️ Generating fix via {MODEL}...")
        raw_response = get_fixed_code(current_code, log_content, supporting_context, attempt)
    
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