#!/usr/bin/env python3
"""
GPT Dog Setup Helper

This script helps configure automatic startup settings for gpt_dog.py.
It allows users to select a character, persona, preset, API provider, model,
and API key, then saves these choices for automatic use when gpt_dog.py runs.
"""

import os
import sys
import json
import argparse
from pathlib import Path

# Try to import from the same files used by gpt_dog.py
try:
    from openai_helper import OpenAiHelper, APIFactory
    from gpt_dog import (
        load_character_cards, select_character, view_character,
        load_persona_cards, select_persona, view_persona,
        load_preset_cards, select_preset, view_preset,
        find_character_by_name, find_persona_by_name, find_preset_by_name
    )
except ImportError:
    print("\033[31mError importing from gpt_dog.py. Make sure you're in the correct directory.\033[0m")
    sys.exit(1)

# Get the current directory
current_path = os.path.dirname(os.path.abspath(__file__))

# Configuration file path
CONFIG_FILE = os.path.join(current_path, "auto_launch_config.json")
AUTO_LAUNCH_FLAG = os.path.join(current_path, "AUTO_LAUNCH")

def color_print(text, color="green"):
    """Print colored text to the console"""
    colors = {
        "green": "\033[32m",
        "yellow": "\033[33m",
        "red": "\033[31m",
        "blue": "\033[34m",
        "reset": "\033[0m"
    }
    print(f"{colors.get(color, '')}{text}{colors['reset']}")

def load_current_config():
    """Load the current auto-launch configuration if it exists"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            color_print(f"Error loading config: {e}", "red")
    return {}

def save_config(config):
    """Save the configuration to the config file"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        color_print(f"Configuration saved to {CONFIG_FILE}", "green")
        return True
    except Exception as e:
        color_print(f"Error saving config: {e}", "red")
        return False

def set_auto_launch(enabled):
    """Enable or disable auto-launch by creating or removing the flag file"""
    if enabled:
        # Create the flag file
        try:
            with open(AUTO_LAUNCH_FLAG, 'w') as f:
                f.write("Auto-launch enabled")
            color_print("Auto-launch enabled. gpt_dog.py will use these settings automatically.", "green")
        except Exception as e:
            color_print(f"Error enabling auto-launch: {e}", "red")
    else:
        # Remove the flag file if it exists
        if os.path.exists(AUTO_LAUNCH_FLAG):
            try:
                os.remove(AUTO_LAUNCH_FLAG)
                color_print("Auto-launch disabled. gpt_dog.py will prompt for settings.", "yellow")
            except Exception as e:
                color_print(f"Error disabling auto-launch: {e}", "red")

def is_auto_launch_enabled():
    """Check if auto-launch is enabled"""
    return os.path.exists(AUTO_LAUNCH_FLAG)

def select_api_provider():
    """Select the API provider interactively"""
    color_print("\n=== API Provider Selection ===", "blue")
    providers = [
        {"name": "OpenAI", "id": "openai"},
        {"name": "Anthropic/Claude", "id": "anthropic"},
        {"name": "OpenRouter", "id": "openrouter"},
        {"name": "Custom API", "id": "custom"}
    ]
    
    for i, provider in enumerate(providers):
        print(f"{i+1}. {provider['name']}")
    
    while True:
        try:
            choice = int(input("\nSelect API provider (1-4): "))
            if 1 <= choice <= len(providers):
                return providers[choice-1]["id"]
            else:
                color_print("Invalid choice. Please try again.", "red")
        except ValueError:
            color_print("Please enter a number.", "red")

def collect_api_details(provider):
    """Collect API details based on the selected provider"""
    details = {"provider": provider}
    
    # API Key
    api_key = input(f"\nEnter your {provider.upper()} API key: ").strip()
    if api_key:
        details["api_key"] = api_key
    
    # For OpenAI, collect assistant ID
    if provider == "openai":
        assistant_id = input("\nEnter your OpenAI Assistant ID: ").strip()
        if assistant_id:
            details["assistant_id"] = assistant_id
        assistant_name = input("\nEnter your Assistant name [PiDog]: ").strip() or "PiDog"
        details["assistant_name"] = assistant_name
    
    # For custom API, collect URL
    if provider == "custom":
        api_url = input("\nEnter your custom API URL: ").strip()
        if api_url:
            details["api_url"] = api_url
        else:
            api_url = "https://api.openai.com"  # Default if none provided
            details["api_url"] = api_url
    
    # For non-OpenAI providers, collect model name
    if provider != "openai":
        # Fetch available models if possible
        try:
            color_print("\nFetching available models from your API...", "blue")
            
            # Import requests for API calls
            import requests
            models_url = ""
            
            if provider == "custom":
                # For custom providers, construct the models endpoint based on the API URL
                if api_url.endswith('/openai'):
                    models_url = f"{api_url}/models"
                else:
                    models_url = f"{api_url}/v1/models"
            elif provider == "openrouter":
                models_url = "https://openrouter.ai/api/v1/models"
            elif provider == "anthropic":
                # Anthropic doesn't have a models endpoint for API v1
                # Just use the default models
                default_models = ["claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307"]
                print("\nAvailable Claude models:")
                for i, model in enumerate(default_models):
                    print(f"{i+1}. {model}")
                
                try:
                    choice = int(input("\nSelect a model (or 0 to enter custom): "))
                    if 1 <= choice <= len(default_models):
                        model_name = default_models[choice-1]
                    else:
                        model_name = input("\nEnter custom model name: ").strip()
                except ValueError:
                    model_name = input("\nEnter custom model name: ").strip()
                
                details["model_name"] = model_name
                return details
            
            headers = {"Authorization": f"Bearer {api_key}"}
            
            response = requests.get(models_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                models_data = response.json()
                
                if 'data' in models_data:
                    models = [model.get('id') for model in models_data.get('data', [])]
                else:
                    models = [model.get('id') for model in models_data]
                
                if models:
                    print("\nAvailable models:")
                    for i, model in enumerate(models):
                        print(f"{i+1}. {model}")
                    
                    print(f"{len(models)+1}. Enter custom model name")
                    
                    model_choice = input("\nSelect a model by number: ").strip()
                    
                    try:
                        model_index = int(model_choice) - 1
                        if 0 <= model_index < len(models):
                            details["model_name"] = models[model_index]
                        else:
                            custom_model = input("\nEnter custom model name: ").strip()
                            details["model_name"] = custom_model
                    except ValueError:
                        custom_model = input("\nEnter custom model name: ").strip()
                        details["model_name"] = custom_model
                else:
                    color_print("\nNo models found. You'll need to specify the model manually.", "yellow")
                    details["model_name"] = input("\nEnter model name: ").strip()
            else:
                color_print(f"\nFailed to fetch models: {response.status_code} {response.text}", "yellow")
                default_model = "gpt-4" if provider == "custom" else "openai/gpt-4"
                details["model_name"] = input(f"\nEnter model name [{default_model}]: ").strip() or default_model
        except Exception as e:
            color_print(f"\nError fetching models: {e}", "yellow")
            default_model = "gpt-4" if provider == "custom" else "openai/gpt-4"
            details["model_name"] = input(f"\nEnter model name [{default_model}]: ").strip() or default_model
    
    return details

def main():
    """Main function to run the setup"""
    parser = argparse.ArgumentParser(description='Setup auto-launch configuration for GPT Dog')
    parser.add_argument('--disable', action='store_true', help='Disable auto-launch')
    parser.add_argument('--status', action='store_true', help='Show current auto-launch status and exit')
    args = parser.parse_args()
    
    # Check if just viewing status
    if args.status:
        current_config = load_current_config()
        enabled = is_auto_launch_enabled()
        
        color_print("\n=== GPT Dog Auto-Launch Status ===", "blue")
        color_print(f"Auto-launch: {'Enabled' if enabled else 'Disabled'}", "green" if enabled else "yellow")
        
        if current_config:
            color_print("\nCurrent configuration:", "blue")
            character = current_config.get("character", "Not set")
            persona = current_config.get("persona", "Not set")
            preset = current_config.get("preset", "Not set")
            provider = current_config.get("api_config", {}).get("provider", "Not set")
            model = current_config.get("api_config", {}).get("model_name", "Default")
            
            print(f"Character: {character}")
            print(f"Persona: {persona}")
            print(f"Preset: {preset}")
            print(f"API Provider: {provider}")
            print(f"Model: {model}")
        else:
            color_print("No configuration found.", "yellow")
        
        return
    
    # Check if disabling auto-launch
    if args.disable:
        set_auto_launch(False)
        return
    
    # Display header
    color_print("\n" + "=" * 60, "blue")
    color_print("GPT Dog Auto-Launch Setup", "blue")
    color_print("=" * 60, "blue")
    color_print("This utility will help you configure automatic startup settings for GPT Dog.")
    color_print("You'll select a character, persona, preset, and API settings.")
    print()
    
    # Load current config if it exists
    current_config = load_current_config()
    if current_config:
        color_print("Current configuration found!", "green")
        use_current = input("Use current configuration as a starting point? (y/n) [y]: ").lower() or "y"
        if use_current != "y":
            current_config = {}
    
    # Initialize the configuration
    config = {}
    
    # Select Character
    color_print("\nStep 1: Select a Character", "blue")
    if current_config and "character" in current_config:
        current_char = current_config["character"]
        use_current = input(f"Keep current character '{current_char}'? (y/n) [y]: ").lower() or "y"
        if use_current == "y":
            character = find_character_by_name(current_char)
            if character:
                config["character"] = current_char
                view_character(character)
            else:
                color_print(f"Character '{current_char}' not found.", "red")
                character = select_character()
                config["character"] = character["name"]
        else:
            character = select_character()
            config["character"] = character["name"]
    else:
        character = select_character()
        config["character"] = character["name"]
    
    # Select Persona
    color_print("\nStep 2: Select a Persona", "blue")
    if current_config and "persona" in current_config:
        current_persona = current_config["persona"]
        use_current = input(f"Keep current persona '{current_persona}'? (y/n) [y]: ").lower() or "y"
        if use_current == "y":
            persona = find_persona_by_name(current_persona)
            if persona:
                config["persona"] = current_persona
                view_persona(persona)
            else:
                color_print(f"Persona '{current_persona}' not found.", "red")
                persona = select_persona()
                config["persona"] = persona["name"]
        else:
            persona = select_persona()
            config["persona"] = persona["name"]
    else:
        persona = select_persona()
        config["persona"] = persona["name"]
    
    # Select Preset
    color_print("\nStep 3: Select a Preset", "blue")
    if current_config and "preset" in current_config:
        current_preset = current_config["preset"]
        use_current = input(f"Keep current preset '{current_preset}'? (y/n) [y]: ").lower() or "y"
        if use_current == "y":
            preset = find_preset_by_name(current_preset)
            if preset:
                config["preset"] = current_preset
                view_preset(preset)
            else:
                color_print(f"Preset '{current_preset}' not found.", "red")
                preset = select_preset()
                config["preset"] = preset["name"]
        else:
            preset = select_preset()
            config["preset"] = preset["name"]
    else:
        preset = select_preset()
        config["preset"] = preset["name"]
    
    # API Configuration
    color_print("\nStep 4: API Configuration", "blue")
    if current_config and "api_config" in current_config:
        current_api = current_config["api_config"]
        current_provider = current_api.get("provider", "unknown")
        use_current = input(f"Keep current API configuration (provider: {current_provider})? (y/n) [y]: ").lower() or "y"
        if use_current == "y":
            config["api_config"] = current_api
        else:
            provider = select_api_provider()
            api_config = collect_api_details(provider)
            config["api_config"] = api_config
    else:
        provider = select_api_provider()
        api_config = collect_api_details(provider)
        config["api_config"] = api_config
    
    # Input Mode
    color_print("\nStep 5: Input Mode", "blue")
    if current_config and "input_mode" in current_config:
        current_mode = current_config["input_mode"]
        use_current = input(f"Keep current input mode '{current_mode}'? (y/n) [y]: ").lower() or "y"
        if use_current == "y":
            config["input_mode"] = current_mode
        else:
            mode = input("Select input mode (voice/keyboard) [keyboard]: ").lower() or "keyboard"
            config["input_mode"] = "voice" if mode.startswith("v") else "keyboard"
    else:
        mode = input("Select input mode (voice/keyboard) [keyboard]: ").lower() or "keyboard"
        config["input_mode"] = "voice" if mode.startswith("v") else "keyboard"
    
    # Image Support
    color_print("\nStep 6: Image Support", "blue")
    if current_config and "with_img" in current_config:
        current_img = current_config["with_img"]
        use_current = input(f"Keep image support {'enabled' if current_img else 'disabled'}? (y/n) [y]: ").lower() or "y"
        if use_current == "y":
            config["with_img"] = current_img
        else:
            img_support = input("Enable image support? (y/n) [y]: ").lower() or "y"
            config["with_img"] = img_support.startswith("y")
    else:
        img_support = input("Enable image support? (y/n) [y]: ").lower() or "y"
        config["with_img"] = img_support.startswith("y")
    
    # Save the configuration
    if save_config(config):
        # Ask if they want to enable auto-launch
        enable = input("\nEnable auto-launch with these settings? (y/n) [y]: ").lower() or "y"
        set_auto_launch(enable.startswith("y"))
        
        color_print("\nSetup complete!", "green")
        color_print("To launch GPT Dog with these settings, run: python gpt_dog.py", "green")
        color_print("To disable auto-launch later, run: python setup_gpt_dog.py --disable", "green")
        color_print("To check status, run: python setup_gpt_dog.py --status", "green")
    else:
        color_print("\nSetup failed to save configuration.", "red")

if __name__ == "__main__":
    main() 