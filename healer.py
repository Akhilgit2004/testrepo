# In get_diagnosis function
res = requests.post(
    url,
    json={"model": MODEL, "prompt": prompt, "stream": False},
    timeout=300  # Increased from 120 to 300 seconds
)

# In get_fixed_code function
res = requests.post(
    url,
    json={"model": MODEL, "prompt": prompt, "stream": False, "options": {"temperature": 0.1}},
    timeout=600  # Increased from 300 to 600 seconds
)