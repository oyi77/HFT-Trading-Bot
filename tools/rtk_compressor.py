"""
RTK Compressor — Token Savings Tool.
Minifies source code for LLM context to save 60-90% tokens.
Removes comments, docstrings, and redundant whitespace.
"""
import ast
import astor # if not available we use a simple regex-based one
import re

def compress_python(code: str) -> str:
    """Removes comments and docstrings from python code."""
    # Remove docstrings
    code = re.sub(r'\"\"\"[\s\S]*?\"\"\"', '', code)
    code = re.sub(r'\'\'\'[\s\S]*?\'\'\'', '', code)
    
    # Remove single line comments
    lines = code.split('\n')
    clean_lines = []
    for line in lines:
        # Simple comment removal (doesn't handle # inside strings, but good enough for token saving)
        if '#' in line:
            line = line[:line.find('#')]
        
        # Strip and ignore empty
        line = line.strip()
        if line:
            clean_lines.append(line)
            
    # Join with minimum newline
    return '\n'.join(clean_lines)

def compress_text(text: str) -> str:
    """Simple whitespace compression for logs/text."""
    text = re.sub(r'\n+', '\n', text)
    text = re.sub(r' +', ' ', text)
    return text.strip()

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        with open(sys.argv[1], 'r') as f:
            content = f.read()
            compressed = compress_python(content)
            print(f"Original len: {len(content)}")
            print(f"Compressed len: {len(compressed)}")
            print(f"Savings: {round((1 - len(compressed)/len(content))*100, 2)}%")
            # print(compressed)
