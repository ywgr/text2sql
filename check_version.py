#!/usr/bin/env python3
"""
Version checker for TEXT2SQL files
This script helps identify which version you're running and ensures you're using the correct one.
"""

import os
import re

def check_file_version(filename):
    """Check the version of a TEXT2SQL file"""
    if not os.path.exists(filename):
        return None, "File not found"
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Look for version indicators
        version_patterns = [
            r'V2\.5',
            r'V2\.4', 
            r'V2\.3',
            r'V2\.2',
            r'V2\.0',
            r'V1\.0'
        ]
        
        found_versions = []
        for pattern in version_patterns:
            if re.search(pattern, content):
                found_versions.append(pattern)
        
        # Check for Text2SQLSystemV23 vs Text2SQLQueryEngine
        if 'Text2SQLSystemV23' in content:
            class_type = "Text2SQLSystemV23 (Old version)"
        elif 'Text2SQLQueryEngine' in content:
            class_type = "Text2SQLQueryEngine (V2.5)"
        else:
            class_type = "Unknown class type"
            
        return found_versions, class_type
        
    except Exception as e:
        return None, f"Error reading file: {e}"

def main():
    print("🔍 TEXT2SQL Version Checker")
    print("=" * 50)
    
    # List all text2sql files
    text2sql_files = [f for f in os.listdir('.') if f.startswith('text2sql') and f.endswith('.py')]
    
    if not text2sql_files:
        print("❌ No text2sql files found in current directory")
        return
    
    print("📁 Found TEXT2SQL files:")
    print()
    
    for filename in sorted(text2sql_files):
        versions, class_type = check_file_version(filename)
        
        if versions:
            version_str = ", ".join(versions)
            status = "✅ RECOMMENDED" if "V2.5" in version_str and "Text2SQLQueryEngine" in class_type else "⚠️  OLD VERSION"
            print(f"{filename}:")
            print(f"  Version: {version_str}")
            print(f"  Class Type: {class_type}")
            print(f"  Status: {status}")
            print()
        else:
            print(f"{filename}: {class_type}")
            print()
    
    print("=" * 50)
    print("📋 Instructions:")
    print("1. Use text2sql_v2.5_ui.py for the latest version")
    print("2. The error 'Text2SQLSystemV23 is not defined' occurs with older versions")
    print("3. Make sure you have all dependencies installed: pip install -r requirements.txt")
    print("4. Run with: streamlit run text2sql_v2.5_ui.py")

if __name__ == "__main__":
    main()