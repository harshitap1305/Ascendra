import os
import re

directory = 'src'

replacements = {
    r'\btext-white\b': 'text-secondary',
    r'\bbg-slate-950\b': 'bg-cream',
    r'\bbg-slate-900\b': 'bg-tan',
    r'\bbg-slate-800\b': 'bg-tan',
    r'\btext-slate-100\b': 'text-secondary',
    r'\btext-slate-200\b': 'text-secondary',
    r'\btext-slate-300\b': 'text-secondary',
    r'\btext-slate-400\b': 'text-secondary/70',
    r'\btext-slate-500\b': 'text-secondary/70',
    r'\bborder-slate-800\b': 'border-secondary',
    r'\bborder-slate-700\b': 'border-secondary',
    r'\bborder-slate-600\b': 'border-secondary',
}

for root, dirs, files in os.walk(directory):
    for file in files:
        if file.endswith('.jsx') or file.endswith('.js'):
            filepath = os.path.join(root, file)
            with open(filepath, 'r') as f:
                content = f.read()
            
            new_content = content
            for old, new in replacements.items():
                new_content = re.sub(old, new, new_content)
            
            if new_content != content:
                with open(filepath, 'w') as f:
                    f.write(new_content)
                print(f"Updated {filepath}")
