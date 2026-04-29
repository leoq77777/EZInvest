#!/usr/bin/env python3
import argparse
import os
import sys
from pathlib import Path

def update_env(key: str, value: str, env_path: Path):
    """Update or add a key-value pair in the .env file."""
    lines = []
    if env_path.exists():
        with open(env_path, "r") as f:
            lines = f.readlines()
    
    found = False
    new_lines = []
    for line in lines:
        if line.strip().startswith(f"{key}="):
            new_lines.append(f"{key}={value}\n")
            found = True
        else:
            new_lines.append(line)
    
    if not found:
        new_lines.append(f"{key}={value}\n")
    
    with open(env_path, "w") as f:
        f.writelines(new_lines)

def main():
    parser = argparse.ArgumentParser(description="EZInvest Configuration Manager")
    parser.add_argument("--provider", choices=["local", "openai", "deepseek"], help="Set the LLM provider")
    parser.add_argument("--set-key", help="Set the API key for the provider")
    parser.add_argument("--status", action="store_true", help="Show current configuration status")
    
    args = parser.parse_args()
    
    # Root of the project (one level up from scripts/)
    project_root = Path(__file__).resolve().parent.parent.parent
    env_path = project_root / ".env"
    
    if not env_path.exists():
        # Try to copy from example if it doesn't exist
        example_path = project_root / ".env.example"
        if example_path.exists():
            print(f"Creating .env from .env.example...")
            import shutil
            shutil.copy(example_path, env_path)
    
    if args.provider:
        update_env("LLM_PROVIDER", args.provider, env_path)
        print(f"✅ LLM provider set to: {args.provider}")
        
    if args.set_key:
        if not args.provider and not os.environ.get("LLM_PROVIDER"):
            # If no provider is specified, try to read from .env
            current_provider = "local"
            if env_path.exists():
                with open(env_path, "r") as f:
                    for line in f:
                        if line.startswith("LLM_PROVIDER="):
                            current_provider = line.split("=")[1].strip()
                            break
            target_provider = current_provider
        else:
            target_provider = args.provider or os.environ.get("LLM_PROVIDER")
        
        key_name = f"{target_provider.upper()}_API_KEY"
        update_env(key_name, args.set_key, env_path)
        print(f"✅ API key set for provider: {target_provider}")

    if args.status or (not args.provider and not args.set_key):
        print("\n--- Current Configuration Status ---")
        if env_path.exists():
            with open(env_path, "r") as f:
                for line in f:
                    if any(x in line for x in ["LLM_PROVIDER", "API_KEY", "MODEL"]):
                        # Mask API keys
                        if "API_KEY" in line and "=" in line:
                            k, v = line.split("=", 1)
                            v = v.strip()
                            masked = v[:4] + "*" * (len(v) - 8) + v[-4:] if len(v) > 8 else "****"
                            print(f"{k}={masked}")
                        else:
                            print(line.strip())
        else:
            print("No .env file found.")

if __name__ == "__main__":
    main()
