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
    """Fetches the latest Jenkins build log with a 500-line buffer."""
    job_name = os.environ.get('JOB_NAME', 'unknown_job')
    build_id = os.environ.get('BUILD_ID', 'unknown_build')
    log_path = f"/var/lib/jenkins/jobs/{job_name}/builds/{build_id}/log"
    try:
        with open(log_path, 'r') as f:
            lines = f.readlines()
            return "".join(lines[-500:])
    except Exception as e:
        return f"Could not read log: {e}"

def verify_fix(target_file):
    """Dynamically detects the build system and verifies the code."""
    print(f"🧪 VERIFICATION: Running compiler check on {target_file}...")
    compile_cmd = []
    
    if os.path.exists("Makefile"): compile_cmd = ['make']
    elif os.path.exists("pom.xml"): compile_cmd = ['mvn', 'clean', 'compile']
    elif target_file.endswith(".java"): compile_cmd = ['javac', target_file]
    elif target_file.endswith(".cpp") or target_file.endswith(".c"): compile_cmd = ['g++', target_file, '-o', 'test_build']
    elif target_file.endswith(".py"): compile_cmd = ['python3', '-m', 'py_compile', target_file]
    
    if not compile_cmd: return True, ""

    result = subprocess.run(compile_cmd, capture_output=True, text=True)
    return (result.returncode == 0, result.stderr)

def create_pull_request(explanation, target_file, attempt):
    """Commits code and opens a GitHub Pull Request using GITHUB_TOKEN."""
    build_id = os.environ.get('BUILD_ID', 'manual')
    branch_name = f"healer-fix-{build_id}"
    gh_token = os.environ.get('GITHUB_TOKEN')
    repo_url = os.environ.get('GIT_URL')

    try:
        subprocess.run(['git', 'config', 'user.name', 'Healer Agent'], check=True)
        subprocess.run(['git', 'config', 'user.email', 'healer@agent.ai'], check=True)

        if gh_token and repo_url:
            auth_url = repo_url.replace("https://", f"https://{gh_token}@")
            subprocess.run(['git', 'remote', 'set-url', 'origin', auth_url], check=True)

        subprocess.run(['git', 'checkout', '-b', branch_name], check=True)
        subprocess.run(['git', 'add', target_file], check=True)
        subprocess.run(['git', 'commit', '-m', f"fix: AI repair for {target_file}"], check=True)
        subprocess.run(['git', 'push', '-u', 'origin', branch_name], check=True)
        
        pr_body = f"## 🚨 Automated Fix Report\n**Diagnosis:**\n{explanation}"
        subprocess.run(['gh', 'pr', 'create', '--title', f"🤖 AI Fix: {target_file}", '--body', pr_body, '--head', branch_name, '--base', 'main'], check=True)
        return True
    except Exception as e:
        print(f"❌ Git Error: {e}")
        return False

# ==========================================
# AI AGENT FUNCTIONS
# ==========================================

def get_diagnosis(file_content, error_log, supporting_context=""):
    """STAGE 1: Now with 100% more peripheral vision."""
    url = "http://localhost:11434/api/generate"
    prompt = f"""You are a Senior SRE. Analyze the build failure.
    
    ERROR LOG:
    {error_log}

    BROKEN SOURCE CODE:
    {file_content}

    SUPPORTING CONTEXT (Related files):
    {supporting_context}
    
    TASK: Identify if the error is in the broken file or caused by a mismatch with supporting files.
    DIAGNOSIS:"""
    
    try:
        res = requests.post(url, json={"model": MODEL, "prompt": prompt, "stream": False}, timeout=120)
        return res.json().get("response", "Could not generate diagnosis.")
    except Exception as e:
        return f"API Error: {e}"

def get_fixed_code(target_file, file_content, diagnosis):
    """STAGE 2: Generate the full rewritten file based on the diagnosis."""
    url = "http://localhost:11434/api/generate"
    
    # We now pass the target_file into the prompt to give the AI spatial awareness
    prompt = f"""You are an automated code fixer. 
    Based on the following diagnosis, fix the provided source code.
    
    DIAGNOSIS:
    {diagnosis}
    
    FILE NAME: {target_file}
    
    SOURCE CODE:
    {file_content}
    
    TASK: Output the ENTIRE corrected source file. Do not truncate. 
    Wrap the code in a single Markdown block (```).
    
    CRITICAL RULES:
    1. DO NOT alter the class name, capitalization, or access modifiers (like adding 'public').
    2. The class name must perfectly align with the FILE NAME.
    3. Only fix the specific error mentioned in the diagnosis."""
    
    try:
        res = requests.post(url, json={"model": MODEL, "prompt": prompt, "stream": False, "options": {"temperature": 0.1}}, timeout=300)
        return res.json().get("response", "")
    except Exception as e:
        return ""
    
def get_supporting_context(content, current_file_path):
    """Scans the file for local imports and returns their content as context."""
    directory = os.path.dirname(current_file_path) or "."
    supporting_data = ""
    
    # Simple regex to find potential local file references
    # Java: import com.pkg.ClassName; -> ClassName.java
    # Python: from module import ... -> module.py
    # C++: #include "header.h" -> header.h
    patterns = [
        r'import\s+[\w.]+\.(\w+);',       # Java imports
        r'from\s+(\w+)\s+import',         # Python local imports
        r'#include\s+"([^"]+)"'           # C++ local headers
    ]
    
    found_files = []
    for pattern in patterns:
        matches = re.findall(pattern, content)
        for match in matches:
            # Try various extensions for the found name
            for ext in ['.java', '.py', '.cpp', '.h']:
                potential_file = os.path.join(directory, f"{match}{ext}" if not match.endswith(ext) else match)
                if os.path.exists(potential_file) and potential_file != current_file_path:
                    found_files.append(potential_file)

    # Read the content of the found supporting files
    for file in list(set(found_files))[:3]: # Limit to 3 files to save tokens
        try:
            with open(file, 'r') as f:
                supporting_data += f"\n--- SUPPORTING CONTEXT: {file} ---\n{f.read()}\n"
        except:
            continue
            
    return supporting_data
# ==========================================
# MAIN ORCHESTRATOR
# ==========================================

if __name__ == "__main__":
    print("\n" + "="*50)
    print("🚨 HYBRID HEALER AGENT: INITIATING RECOVERY...")
    
    log_content = get_latest_jenkins_log()
    
    # 1. Target Acquisition (Bottom-Up Search + Ignore List)
    potential_files = re.findall(r'(\b[a-zA-Z0-9_./-]+\.(?:cpp|py|java|js|c|h))\b', str(log_content))
    ignore_list = ["package.json", "package-lock.json", "pom.xml", "Makefile", "build.gradle", "healer.py"]
    
    target_file = None
    for file_path in reversed(potential_files):
        clean_path = file_path.strip()
        if any(ignored in clean_path for ignored in ignore_list) or "://" in clean_path:
            continue
        if os.path.exists(clean_path):
            target_file = clean_path
            print(f"🎯 Target confirmed: {target_file}")
            break

    if not target_file:
        print("💀 ERROR: Could not find a valid source file in the logs. Aborting.")
        exit(1)

    with open(target_file, 'r') as f:
        original_code = f.read()

    success = False
    for attempt in range(1, MAX_RETRIES + 1):
        print(f"\n🔄 ATTEMPT {attempt}/{MAX_RETRIES}...")
        
        # STAGE 1: Reasoning
        print("🧠 STAGE 1: Diagnosing with local context...")
        context = get_supporting_context(original_code, target_file)
        if context:
            print(f"👀 Found supporting context in related files.")
            
        diagnosis = get_diagnosis(original_code, log_content, context)
        print(f"\n🗣️ AI DIAGNOSIS:\n{diagnosis}\n")
        
        # STAGE 2: Coding
        print("🛠️ STAGE 2: Generating full file rewrite...")
        raw_response = get_fixed_code(target_file, original_code, diagnosis)
        print(f"\n🤖 AI RAW CODE RESPONSE:\n{raw_response[:200]}... [TRUNCATED FOR LOGS]\n")
        
        code_block_match = re.search(r"`{3}(?:[a-zA-Z0-9_+-]+)?\n(.*?)\n`{3}", raw_response, re.DOTALL)
        
        if code_block_match:
            fixed_code = code_block_match.group(1).strip()
            with open(target_file, 'w') as f:
                f.write(fixed_code)
                
            # STAGE 3: Verification
            verified, errors = verify_fix(target_file)
            if verified:
                print("✅ VERIFIED: Fix compiled successfully!")
                create_pull_request(diagnosis, target_file, attempt)
                success = True
                break
            else:
                print(f"❌ Verification failed. Compiler said:\n{errors}")
                print("⏪ Reverting file for next attempt...")
                with open(target_file, 'w') as f:
                    f.write(original_code)
        else:
            print("❌ ERROR: AI did not provide a markdown code block.")

    if not success:
        print("💀 ALL ATTEMPTS FAILED. Human intervention required.")
    print("="*50)