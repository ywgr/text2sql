#!/usr/bin/env python3
"""
Setup and run script for TEXT2SQL V2.5 UI
This script will:
1. Install required dependencies
2. Verify the correct file is being run
3. Provide instructions for running the application
"""

import subprocess
import sys
import os

def install_dependencies():
    """Install required dependencies"""
    print("Installing required dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependencies installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False

def verify_file():
    """Verify that the correct file is being run"""
    print("Verifying TEXT2SQL V2.5 UI file...")
    
    # Check if the main file exists
    if not os.path.exists("text2sql_v2.5_ui.py"):
        print("❌ text2sql_v2.5_ui.py not found!")
        return False
    
    # Check if the required module exists
    if not os.path.exists("text2sql_2_5_query.py"):
        print("❌ text2sql_2_5_query.py not found!")
        return False
    
    print("✅ All required files found!")
    return True

def main():
    print("🚀 TEXT2SQL V2.5 UI Setup")
    print("=" * 50)
    
    # Verify files
    if not verify_file():
        print("\n❌ Setup failed. Please ensure all required files are present.")
        return
    
    # Install dependencies
    if not install_dependencies():
        print("\n❌ Setup failed. Please install dependencies manually:")
        print("pip install -r requirements.txt")
        return
    
    print("\n✅ Setup completed successfully!")
    print("\n📋 To run the application, use one of these commands:")
    print("1. streamlit run text2sql_v2.5_ui.py")
    print("2. python -m streamlit run text2sql_v2.5_ui.py")
    print("\n⚠️  Important: Make sure you're running text2sql_v2.5_ui.py, not any other version!")
    print("   The error 'Text2SQLSystemV23 is not defined' occurs when running older versions.")
    
    # Ask if user wants to run now
    try:
        run_now = input("\n🤔 Would you like to run the application now? (y/n): ").lower().strip()
        if run_now in ['y', 'yes']:
            print("\n🚀 Starting TEXT2SQL V2.5 UI...")
            subprocess.run([sys.executable, "-m", "streamlit", "run", "text2sql_v2.5_ui.py"])
    except KeyboardInterrupt:
        print("\n👋 Setup cancelled by user.")

if __name__ == "__main__":
    main()