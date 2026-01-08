#!/usr/bin/env python3
"""Quick test with llama3.2:1b model (much faster on CPU)"""

import ollama
import time

MODEL = 'llama3.2:1b'  # Much faster!

prompt = """Extract company info as JSON:
- products: array
- services: array  
- customers: array

Text: MagiQ AI is a sales intelligence platform. Products: Win Probability Score, AI-generated sales strategies.

Return only JSON:"""

print(f"Testing {MODEL}...")
print("This should complete in 10-30 seconds...")
print()

start = time.time()
try:
    response = ollama.chat(
        model=MODEL,
        messages=[{'role': 'user', 'content': prompt}],
        options={'temperature': 0.1, 'num_ctx': 2048}
    )
    elapsed = time.time() - start
    print(f"✅ SUCCESS in {elapsed:.1f}s")
    print()
    print("Response:")
    print(response['message']['content'])
except Exception as e:
    elapsed = time.time() - start
    print(f"❌ FAILED after {elapsed:.1f}s: {e}")

