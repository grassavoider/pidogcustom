from openai_helper import OpenAiHelper, APIFactory
from keys import OPENAI_API_KEY, OPENAI_ASSISTANT_ID
from action_flow import ActionFlow
from utils import *
from pidog import Pidog

#import readline # optimize keyboard input, only need to import

import time
import threading
import random
import os
import sys
import json
import argparse

# Global variables
input_mode = 'keyboard'  # Default to keyboard mode
speech_recognition_available = False

# Check for auto-launch configuration
AUTO_LAUNCH_FLAG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "AUTO_LAUNCH")
AUTO_LAUNCH_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auto_launch_config.json")

def load_auto_launch_config():
    """Load the auto-launch configuration if enabled"""
    if os.path.exists(AUTO_LAUNCH_FLAG) and os.path.exists(AUTO_LAUNCH_CONFIG):
        try:
            with open(AUTO_LAUNCH_CONFIG, 'r', encoding='utf-8') as f:
                config = json.load(f)
                print("\033[32mLoaded auto-launch configuration\033[0m")
                return config
        except Exception as e:
            print(f"\033[31mError loading auto-launch configuration: {e}\033[0m")
    return None

auto_launch_config = load_auto_launch_config()
if auto_launch_config:
    # Set input mode from config
    if "input_mode" in auto_launch_config:
        input_mode = auto_launch_config["input_mode"]
        print(f"\033[32mAuto-configured input mode: {input_mode}\033[0m")
    
    # Set image support from config
    if "with_img" in auto_launch_config:
        with_img = auto_launch_config["with_img"]
        print(f"\033[32mAuto-configured image support: {'enabled' if with_img else 'disabled'}\033[0m")

# Check for speech_recognition availability
try:
    import speech_recognition as sr
    # Check if PyAudio is available without initializing a microphone
    try:
        sr.Microphone  # This will raise an error if PyAudio is not installed
        speech_recognition_available = True
        # Only set to voice mode if explicitly requested or not specified
        if '--keyboard' not in sys.argv:
            input_mode = 'voice'
    except (AttributeError, ImportError) as e:
        print(f"\033[33mWARNING: PyAudio not available: {e}\033[0m")
        print("\033[33mRunning in keyboard mode. Install PyAudio for voice input.\033[0m")
except ImportError:
    print("\033[33mWARNING: speech_recognition module not found.\033[0m")
    print("\033[33mRunning in keyboard mode. Install speech_recognition for voice input.\033[0m")

current_path = os.path.dirname(os.path.abspath(__file__))
os.chdir(current_path)

# Make sure required directories exist
# =================================================================
tts_dir = os.path.join(current_path, "tts")
if not os.path.exists(tts_dir):
    os.makedirs(tts_dir)
    print(f"\033[32mCreated TTS directory: {tts_dir}\033[0m")
else:
    print(f"\033[32mTTS directory exists: {tts_dir}\033[0m")

# Command line arguments
# =================================================================
parser = argparse.ArgumentParser(description='PiDog with configurable API')

parser.add_argument('--keyboard', action='store_true', help='Use keyboard input instead of voice')
parser.add_argument('--no-img', action='store_true', help='Disable image capture and processing')
parser.add_argument('--no-audio', action='store_true', help='Disable audio playback (TTS will still generate files)')

# API Provider configuration
parser.add_argument('--provider', type=str, default='openai', 
                    choices=['openai', 'anthropic', 'openrouter', 'custom'],
                    help='API provider to use (default: openai)')
parser.add_argument('--api-key', type=str, help='API key (defaults to key in keys.py)')
parser.add_argument('--api-url', type=str, help='Custom API URL (for custom providers)')
parser.add_argument('--model', type=str, help='Model name (for non-OpenAI providers)')
parser.add_argument('--config', type=str, help='Path to JSON configuration file')

# Conversation history management
parser.add_argument('--list-conversations', action='store_true', help='List all saved conversations')
parser.add_argument('--load-conversation', type=str, help='Load a specific conversation file')

# Character management
parser.add_argument('--character', type=str, help='Use specified character (by name or filename)')
parser.add_argument('--list-characters', action='store_true', help='List available characters and exit')

# Add persona and preset management
parser.add_argument('--persona', type=str, help='Use specified persona (by name or filename)')
parser.add_argument('--list-personas', action='store_true', help='List available personas and exit')
parser.add_argument('--preset', type=str, help='Use specified preset (by name or filename)')
parser.add_argument('--list-presets', action='store_true', help='List available presets and exit')

# Add a new command-line argument for interactive mode
parser.add_argument('--non-interactive', action='store_true', help='Skip interactive API setup')
parser.add_argument('--interactive', action='store_true', help='Force interactive API setup, overriding other arguments')
parser.add_argument('--verbose', action='store_true', help='Show detailed information even when using auto-launch')

args = parser.parse_args()

# Handle conversation history command-line arguments
# =================================================================
if args.list_conversations:
    # Just list conversations and exit
    load_conversation_history()
    sys.exit(0)

if args.load_conversation:
    # Attempt to load the specified conversation
    loaded_data = load_conversation_history(args.load_conversation)
    if loaded_data:
        print("\033[32mUse the loaded conversation data in your API handler\033[0m")
        # You could automatically set the provider and model based on the loaded conversation
        # (not implemented in this version)
    else:
        sys.exit(1)

# Handle character management arguments
# =================================================================
if args.list_characters:
    characters = load_character_cards()
    print("\n\033[32m=== Available Characters ===\033[0m")
    for i, character in enumerate(characters):
        print(f"{i+1}. {character['name']}")
    sys.exit(0)

# Handle persona management arguments
# =================================================================
if args.list_personas:
    personas = load_persona_cards()
    print("\n\033[32m=== Available Personas ===\033[0m")
    for i, persona in enumerate(personas):
        print(f"{i+1}. {persona['name']}")
    sys.exit(0)

# Handle preset management arguments
# =================================================================
if args.list_presets:
    presets = load_preset_cards()
    print("\n\033[32m=== Available Presets ===\033[0m")
    for i, preset in enumerate(presets):
        print(f"{i+1}. {preset['name']}")
    sys.exit(0)

def find_character_by_name(name):
    """Find a character by name or filename"""
    characters = load_character_cards()
    
    # First, try exact name match
    for character in characters:
        if character['name'].lower() == name.lower():
            return character
    
    # Try filename match (without .json extension)
    for character in characters:
        filename = character['name'].lower().replace(' ', '_')
        if filename == name.lower() or filename == name.lower().replace('.json', ''):
            return character
    
    return None

# Add similar functions for finding personas and presets by name
def find_persona_by_name(name):
    """Find a persona by name or filename"""
    personas = load_persona_cards()
    
    # First, try exact name match
    for persona in personas:
        if persona['name'].lower() == name.lower():
            return persona
    
    # Try filename match (without .json extension)
    for persona in personas:
        filename = persona['name'].lower().replace(' ', '_')
        if filename == name.lower() or filename == name.lower().replace('.json', ''):
            return persona
    
    return None

def find_preset_by_name(name):
    """Find a preset by name or filename"""
    presets = load_preset_cards()
    
    # First, try exact name match
    for preset in presets:
        if preset['name'].lower() == name.lower():
            return preset
    
    # Try filename match (without .json extension)
    for preset in presets:
        filename = preset['name'].lower().replace(' ', '_')
        if filename == name.lower() or filename == name.lower().replace('.json', ''):
            return preset
    
    return None

# Input mode and image capture configuration
if args.keyboard:
    input_mode = 'keyboard'  # Override with explicit keyboard flag
with_img = not args.no_img
with_audio = not args.no_audio  # Add audio configuration

# Determine if we should use interactive setup
use_interactive = True  # Default to interactive mode

# Force interactive mode if the special file exists
interactive_file = os.path.join(current_path, 'INTERACTIVE_MODE')
if os.path.exists(interactive_file):
    use_interactive = True
    print(f"Interactive setup FORCED - special file '{interactive_file}' found")
# Force interactive mode if the flag is set
elif args.interactive:
    use_interactive = True
    print("Interactive setup FORCED - using interactive setup regardless of other arguments")
# Otherwise check for presence of API-related arguments
else:
    # Simplify detection of whether arguments were provided
    import sys
    cmd_args = set(sys.argv[1:])
    api_args = {'--provider', '--api-key', '--api-url', '--model', '--config', '--non-interactive'}

    # Check if any API-related arguments were provided
    has_api_args = any(arg.split('=')[0] in api_args for arg in cmd_args if arg.startswith('--'))

    if has_api_args or args.non_interactive or args.config or args.provider or args.api_key or args.api_url or args.model:
        use_interactive = False
        print("Interactive setup disabled - command line arguments provided")
    else:
        print("No API arguments detected - using interactive setup")

print(f"Interactive mode: {'Enabled' if use_interactive else 'Disabled'}")

# Default to configuration from keys.py
api_config = {
    'provider': 'openai',
    'api_key': OPENAI_API_KEY,
    'assistant_id': OPENAI_ASSISTANT_ID,
    'assistant_name': 'PiDog'
}

# Override with config file and command-line arguments
# Process these before initializing the API handler
if args.config:
    file_config = load_config_from_file(args.config)
    api_config.update(file_config)

# Override with command line arguments if provided
if args.provider:
    api_config['provider'] = args.provider
if args.api_key:
    api_config['api_key'] = args.api_key
if args.api_url:
    api_config['api_url'] = args.api_url
if args.model:
    api_config['model_name'] = args.model

# Initialize API handler - moved inside main()
# =================================================================
api_handler = None
openai_helper = None
selected_character = None
selected_persona = None
selected_preset = None

LANGUAGE = []
# LANGUAGE = ['zh', 'en'] # config stt language code, https://en.wikipedia.org/wiki/List_of_ISO_639_language_codes

# VOLUME_DB = 5
VOLUME_DB = 3

# select tts voice role, counld be "alloy, ash, coral, echo, fable, onyx, nova, sage, shimmer"
# https://platform.openai.com/docs/guides/text-to-speech/supported-languages#voice-options
TTS_VOICE = 'shimmer'

VOICE_ACTIONS = ["bark", "bark harder", "pant",  "howling"]

# dog init 
# =================================================================
try:
    my_dog = Pidog()
    time.sleep(1)
except Exception as e:
    raise RuntimeError(e)

action_flow = ActionFlow(my_dog)

# Vilib start
# =================================================================
if with_img:
    try:
        from vilib import Vilib
        import cv2

        Vilib.camera_start(vflip=False,hflip=False)
        Vilib.display(local=False,web=True)

        while True:
            if Vilib.flask_start:
                break
            time.sleep(0.01)

        time.sleep(.5)
        print('\n')
        vilib_available = True
    except ImportError:
        print("\033[33mWARNING: Vilib module not found. Running without camera support.\033[0m")
        with_img = False
        vilib_available = False

# PyAudio and speech recognition setup
# =================================================================
speech_loaded = False
speech_lock = threading.Lock()
tts_file = None

# Initialize recognizer if speech recognition is available
# =================================================================
if speech_recognition_available:
    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_adjustment_damping = 0.16
    recognizer.dynamic_energy_ratio = 1.6
    recognizer.pause_threshold = 1.0
    print("\033[32mSpeech recognition initialized successfully\033[0m")

def speak_hanlder():
    global speech_loaded, tts_file
    while True:
        with speech_lock:
            _isloaded = speech_loaded
        if _isloaded:
            gray_print('speak start')
            my_dog.speak_block(tts_file)
            gray_print('speak done')
            with speech_lock:
                speech_loaded = False
        time.sleep(0.05)

speak_thread = threading.Thread(target=speak_hanlder)
speak_thread.daemon = True


# actions thread
# =================================================================
action_status = 'standby' # 'standby', 'think', 'actions', 'actions_done'
actions_to_be_done = []
action_lock = threading.Lock()

def action_handler():
    global action_status, actions_to_be_done

    standby_actions = ['waiting', 'feet_left_right']
    standby_weights = [1, 0.3]

    action_interval = 5 # seconds
    last_action_time = time.time()

    while True:
        with action_lock:
            _state = action_status
        if _state == 'standby':
            if time.time() - last_action_time > action_interval:
                choice = random.choices(standby_actions, standby_weights)[0]
                action_flow.run(choice)
                last_action_time = time.time()
                action_interval = random.randint(2, 6)
        elif _state == 'think':
            action_flow.run('think')
            last_action_time = time.time()
            pass
        elif _state == 'actions':
            with action_lock:
                _actions = actions_to_be_done
            for _action in _actions:
                try:
                    action_flow.run(_action)
                except Exception as e:
                    print(f'action error: {e}')
                time.sleep(0.5)

            with action_lock:
                action_status = 'actions_done'
            last_action_time = time.time()

        time.sleep(0.01)

action_thread = threading.Thread(target=action_handler)
action_thread.daemon = True


# main
# =================================================================
def main():
    global current_feeling, last_feeling
    global speech_loaded
    global action_status, actions_to_be_done
    global tts_file
    global input_mode  # Add global declaration for input_mode
    global api_config  # Add global declaration for api_config
    global api_handler, openai_helper  # Add global declaration for API handlers
    global selected_character, selected_persona, selected_preset  # Add global declarations for cards
    global auto_launch_config

    my_dog.rgb_strip.close()
    action_flow.change_status(action_flow.STATUS_SIT)
    
    print("\033[32m" + "=" * 60 + "\033[0m")
    print("\033[32mPiDog API Client starting up...\033[0m")
    
    # Check if we're using auto-launch configuration
    using_auto_launch = False
    if auto_launch_config:
        print("\033[32mUsing auto-launch configuration\033[0m")
        using_auto_launch = True
    
    # Character selection
    if using_auto_launch and "character" in auto_launch_config:
        # Use auto-launch character
        char_name = auto_launch_config["character"]
        character = find_character_by_name(char_name)
        if character:
            selected_character = character
            print(f"\033[32mAuto-configured character: {selected_character['name']}\033[0m")
            # Only show detailed view if verbose output is enabled
            if "--verbose" in sys.argv:
                view_character(selected_character)
        else:
            print(f"\033[31mCharacter not found: {char_name}\033[0m")
            print("\033[31mFalling back to interactive character selection\033[0m")
            selected_character = select_character()
            view_character(selected_character)
    elif args.character:
        # Use specified character from command line
        character = find_character_by_name(args.character)
        if character:
            selected_character = character
            print(f"\033[32mUsing character: {selected_character['name']} (from command line)\033[0m")
        else:
            print(f"\033[31mCharacter not found: {args.character}\033[0m")
            print("\033[31mFalling back to interactive character selection\033[0m")
            selected_character = select_character()
            view_character(selected_character)
    else:
        # Interactive character selection
        selected_character = select_character()
        view_character(selected_character)
    
    # Persona selection
    if using_auto_launch and "persona" in auto_launch_config:
        # Use auto-launch persona
        persona_name = auto_launch_config["persona"]
        persona = find_persona_by_name(persona_name)
        if persona:
            selected_persona = persona
            print(f"\033[32mAuto-configured persona: {selected_persona['name']}\033[0m")
            # Only show detailed view if verbose output is enabled
            if "--verbose" in sys.argv:
                view_persona(selected_persona)
        else:
            print(f"\033[31mPersona not found: {persona_name}\033[0m")
            print("\033[31mFalling back to interactive persona selection\033[0m")
            selected_persona = select_persona()
            view_persona(selected_persona)
    elif args.persona:
        # Use specified persona from command line
        persona = find_persona_by_name(args.persona)
        if persona:
            selected_persona = persona
            print(f"\033[32mUsing persona: {selected_persona['name']} (from command line)\033[0m")
        else:
            print(f"\033[31mPersona not found: {args.persona}\033[0m")
            print("\033[31mFalling back to interactive persona selection\033[0m")
            selected_persona = select_persona()
            view_persona(selected_persona)
    else:
        # Interactive persona selection
        selected_persona = select_persona()
        view_persona(selected_persona)
        
    # Preset selection
    if using_auto_launch and "preset" in auto_launch_config:
        # Use auto-launch preset
        preset_name = auto_launch_config["preset"]
        preset = find_preset_by_name(preset_name)
        if preset:
            selected_preset = preset
            print(f"\033[32mAuto-configured preset: {selected_preset['name']}\033[0m")
            # Only show detailed view if verbose output is enabled
            if "--verbose" in sys.argv:
                view_preset(selected_preset)
        else:
            print(f"\033[31mPreset not found: {preset_name}\033[0m")
            print("\033[31mFalling back to interactive preset selection\033[0m")
            selected_preset = select_preset()
            view_preset(selected_preset)
    elif args.preset:
        # Use specified preset from command line
        preset = find_preset_by_name(args.preset)
        if preset:
            selected_preset = preset
            print(f"\033[32mUsing preset: {selected_preset['name']} (from command line)\033[0m")
        else:
            print(f"\033[31mPreset not found: {args.preset}\033[0m")
            print("\033[31mFalling back to interactive preset selection\033[0m")
            selected_preset = select_preset()
            view_preset(selected_preset)
    else:
        # Interactive preset selection
        selected_preset = select_preset()
        view_preset(selected_preset)
    
    # Print summary of selections (compact for auto-launch)
    if using_auto_launch:
        print(f"\033[32mUsing: {selected_character['name']} (character), {selected_persona['name']} (persona), {selected_preset['name']} (preset)\033[0m")
    else:
        print(f"\033[32mUsing character: {selected_character['name']}\033[0m")
        print(f"\033[32mUsing persona: {selected_persona['name']}\033[0m")
        print(f"\033[32mUsing preset: {selected_preset['name']}\033[0m")
    
    # Use interactive setup if needed (unless auto-launch is enabled)
    if using_auto_launch and "api_config" in auto_launch_config:
        # Use auto-launch API configuration
        print("\033[32mUsing auto-configured API settings\033[0m")
        api_config.update(auto_launch_config["api_config"])
    elif use_interactive:
        print("\033[32mStarting interactive API setup...\033[0m")
        interactive_config = interactive_api_setup()
        api_config.update(interactive_config)
    
    # Initialize API handler now that config is finalized
    try:
        # Create appropriate API handler based on provider
        api_handler = APIFactory.create_api_handler(
            api_config['provider'],
            api_config['api_key'],
            **{k: v for k, v in api_config.items() if k != 'provider' and k != 'api_key'}
        )
        
        # For backward compatibility with existing code
        openai_helper = api_handler
        
        # Special case for OpenAI which uses the legacy OpenAiHelper class
        if api_config['provider'] == 'openai':
            openai_helper = OpenAiHelper(
                api_config['api_key'],
                api_config['assistant_id'],
                api_config.get('assistant_name', 'PiDog')
            )
            
            # For OpenAI, set the selected character as instructions
            try:
                if hasattr(openai_helper, 'handler') and hasattr(openai_helper.handler, 'client'):
                    # For the OpenAI assistant API, we need to create a thread with system instructions
                    system_message = openai_helper.handler.client.beta.threads.messages.create(
                        thread_id=openai_helper.handler.thread.id,
                        role="user",
                        content=f"System instructions (not visible to user): {selected_character.get('description', selected_character.get('system_prompt', ''))}"
                    )
                    
                    # Also add persona information
                    if selected_persona and 'system_prompt' in selected_persona:
                        persona_message = openai_helper.handler.client.beta.threads.messages.create(
                            thread_id=openai_helper.handler.thread.id,
                            role="user",
                            content=f"User persona information (not visible to user): {selected_persona['system_prompt']}"
                        )
                    
                    # Apply preset system prompts
                    if selected_preset and 'system_prompts' in selected_preset:
                        for prompt in selected_preset['system_prompts']:
                            preset_message = openai_helper.handler.client.beta.threads.messages.create(
                                thread_id=openai_helper.handler.thread.id,
                                role="user",
                                content=f"System instruction (not visible to user): {prompt}"
                            )
                    
                    print("\033[32mSet character, persona, and preset instructions for OpenAI\033[0m")
            except Exception as e:
                print(f"\033[31mError setting API configuration for OpenAI: {e}\033[0m")
        
        # For other providers, build messages using our unified function
        else:
            if hasattr(api_handler, 'conversation_history'):
                # Build the conversation history using all three cards
                api_handler.conversation_history = build_api_messages(
                    selected_character,
                    selected_persona,
                    selected_preset
                )
                print(f"\033[32mSet character, persona, and preset instructions for {api_config['provider']}\033[0m")
                
                # Apply preset parameters if available
                if selected_preset and 'parameters' in selected_preset:
                    for key, value in selected_preset['parameters'].items():
                        if hasattr(api_handler, key):
                            setattr(api_handler, key, value)
                    print(f"\033[32mApplied preset parameters for {api_config['provider']}\033[0m")
        
        # Log the API configuration being used
        print(f"\033[32mAPI Provider: {api_config['provider']}\033[0m")
        if api_config['provider'] == 'custom':
            print(f"\033[32mAPI URL: {api_config.get('api_url', 'Not specified')}\033[0m")
            print(f"\033[32mModel: {api_config.get('model_name', 'Not specified')}\033[0m")
            
    except Exception as e:
        print(f"\033[31mAPI initialization error: {e}\033[m")
        sys.exit(1)
    
    # Print setup information
    print(f"\033[32mInput Mode: {input_mode}\033[0m")
    print(f"\033[32mAudio Playback: {'Enabled' if with_audio else 'Disabled'}\033[0m")
    print(f"\033[32mImage Capture: {'Enabled' if with_img else 'Disabled'}\033[0m")
    
    # Warn about potential vision issues with proxies
    if with_img and api_config['provider'] == 'custom':
        is_gemini_like = ('google' in api_config.get('api_url', '').lower() or 
                         'gemini' in api_config.get('model_name', '').lower() or
                         'models/' in api_config.get('model_name', ''))
        if is_gemini_like:
            print(f"\033[33mNOTE: Some proxies don't support vision for Gemini models\033[0m")
            print(f"\033[33mIf image requests fail, run with: --no-img\033[0m")
    
    if not speech_recognition_available:
        print("\033[33mNOTE: Voice input is not available because PyAudio is not installed.\033[0m")
        print("\033[33mTo enable voice input, install PyAudio:\033[0m")
        print("\033[33m  - Windows: pip install PyAudio\033[0m")
        print("\033[33m  - Linux: sudo apt-get install python3-pyaudio\033[0m")
        print("\033[33m  - macOS: pip install PyAudio\033[0m")
    elif input_mode == 'voice':
        # Check for FLAC when voice mode is enabled
        if not install_flac_if_needed():
            print("\033[33mVoice recognition may not work properly without FLAC.\033[0m")
            print("\033[33mConsider switching to keyboard mode with --keyboard flag.\033[0m")
    
    print("\033[32m" + "=" * 60 + "\033[0m")

    # Simple TTS directory setup
    tts_dir = os.path.join(current_path, "tts")
    if not os.path.exists(tts_dir):
        os.makedirs(tts_dir)
        print(f"\033[32mCreated TTS directory: {tts_dir}\033[0m")

    # Test basic functionality
    test_functionality()

    speak_thread.start()
    action_thread.start()

    while True:
        if input_mode == 'voice' and speech_recognition_available:
            # listen
            # ----------------------------------------------------------------
            gray_print("listening ...")

            with action_lock:
                action_status = 'standby'
            my_dog.rgb_strip.set_mode('listen', 'cyan', 1)

            _stderr_back = redirect_error_2_null() # ignore error print to ignore ALSA errors
            # If the chunk_size is set too small (default_size=1024), it may cause the program to freeze
            try:
                with sr.Microphone(chunk_size=8192) as source:
                    cancel_redirect_error(_stderr_back) # restore error print
                    recognizer.adjust_for_ambient_noise(source)
                    audio = recognizer.listen(source)

                # stt
                # ----------------------------------------------------------------
                my_dog.rgb_strip.set_mode('boom', 'yellow', 0.5)

                st = time.time()
                if api_config['provider'] == 'openai':
                    _result = openai_helper.stt(audio, language=LANGUAGE)
                else:
                    # Use speech_recognition's built-in STT if API doesn't support it
                    try:
                        _result = recognizer.recognize_google(audio)
                    except Exception as stt_error:
                        print(f"\033[31mGoogle STT error: {stt_error}\033[0m")
                        # Try Whisper API as fallback if available
                        try:
                            if OPENAI_API_KEY:
                                _result = recognizer.recognize_whisper_api(audio, api_key=OPENAI_API_KEY)
                            else:
                                raise Exception("No OpenAI API key for Whisper fallback")
                        except Exception as whisper_error:
                            print(f"\033[31mWhisper fallback error: {whisper_error}\033[0m")
                            _result = False
                            
                gray_print(f"stt takes: {time.time() - st:.3f} s")

                if _result == False or _result == "":
                    print() # new line
                    continue
            except Exception as e:
                error_msg = str(e).lower()
                if "flac" in error_msg:
                    print(f"\033[31mFLAC conversion error: {e}\033[0m")
                    print("\033[33mTo fix this issue, install FLAC:\033[0m")
                    print("\033[33m  - Ubuntu/Debian: sudo apt-get install flac\033[0m")
                    print("\033[33m  - Windows: Download FLAC from https://xiph.org/flac/download.html\033[0m")
                    print("\033[33m  - macOS: brew install flac\033[0m")
                else:
                    print(f"\033[31mError during voice recognition: {e}\033[0m")
                print("\033[33mSwitching to keyboard input mode\033[0m")
                input_mode = 'keyboard'
                continue

        elif input_mode == 'keyboard':
            with action_lock:
                action_status = 'standby'
            my_dog.rgb_strip.set_mode('listen', 'cyan', 1)

            _result = input(f'\033[1;30m{"input: "}\033[0m').encode(sys.stdin.encoding).decode('utf-8')

            if _result == False or _result == "":
                print() # new line
                continue

            my_dog.rgb_strip.set_mode('boom', 'yellow', 0.5)

        else:
            print(f"\033[31mInvalid input mode: {input_mode}\033[0m")
            input_mode = 'keyboard'
            print("\033[33mSwitching to keyboard input mode\033[0m")
            continue

        # chat-gpt
        # ---------------------------------------------------------------- 
        response = {}
        st = time.time()

        with action_lock:
            action_status = 'think'

        # Process request through the appropriate API
        if with_img and 'vilib_available' in globals() and vilib_available:
            try:
                # Use tts directory for image storage to avoid permission issues
                img_path = os.path.join(current_path, 'tts', 'img_input.jpg')
                cv2.imwrite(img_path, Vilib.img)
                
                # Check if image was actually written
                if not os.path.exists(img_path):
                    raise Exception("Failed to write image file")
                
                # Check if this is a Gemini model that might not support vision through proxy
                is_gemini_proxy = (api_config['provider'] == 'custom' and 
                                 ('google' in api_config.get('api_url', '').lower() or 
                                  'gemini' in api_config.get('model_name', '').lower() or
                                  'models/' in api_config.get('model_name', '')))
                
                if is_gemini_proxy:
                    print(f"\033[33mDetected Gemini model through proxy - some proxies don't support vision\033[0m")
                    print(f"\033[33mTrying image request first, will fallback to text-only if it fails\033[0m")
                
                # Use the appropriate API handler for images
                if api_config['provider'] == 'openai':
                    response = openai_helper.dialogue_with_img(_result, img_path)
                else:
                    # For non-OpenAI providers, check if they support images
                    if hasattr(api_handler, 'dialogue_with_img'):
                        response = api_handler.dialogue_with_img(_result, img_path)
                    else:
                        print(f"\033[33mImage processing not supported by {api_config['provider']} provider, using text-only\033[0m")
                        response = api_handler.dialogue(_result)
                        
                # Clean up image file after processing
                try:
                    if os.path.exists(img_path):
                        os.remove(img_path)
                except:
                    pass  # Don't fail if cleanup fails
                    
            except Exception as e:
                error_msg = str(e).lower()
                if 'validation failed' in error_msg and 'content' in error_msg:
                    print(f"\033[33mProxy rejected image request (likely no vision support): {e}\033[0m")
                    print(f"\033[33mFalling back to text-only for this model/proxy combination\033[0m")
                else:
                    print(f"\033[31mError with image capture: {e}\033[0m")
                    
                # Fallback to text-only if image fails
                if api_config['provider'] == 'openai':
                    response = openai_helper.dialogue(_result)
                else:
                    response = api_handler.dialogue(_result)
        else:
            # Text-only processing
            if api_config['provider'] == 'openai':
                response = openai_helper.dialogue(_result)
            else:
                response = api_handler.dialogue(_result)

        gray_print(f'chat takes: {time.time() - st:.3f} s')

        # actions & TTS
        # ---------------------------------------------------------------- 
        try:
            if isinstance(response, dict):
                if 'actions' in response:
                    actions = list(response['actions'])
                else:
                    actions = ['stop']

                if 'answer' in response:
                    answer = response['answer']
                else:
                    answer = ''

                if len(answer) > 0:
                    _actions = list.copy(actions)
                    for _action in _actions:
                        if _action in VOICE_ACTIONS:
                            actions.remove(_action)
            else:
                response = str(response)
                if len(response) > 0:
                    actions = ['stop']
                    answer = response

        except:
            actions = ['stop']
            answer = ''
    
        try:
            # ---- tts ----
            _status = False
            if answer != '':
                st = time.time()
                _time = time.strftime("%y-%m-%d_%H-%M-%S", time.localtime())
                _tts_f = f"./tts/{_time}_raw.wav"
                
                # Use the original working TTS method for OpenAI
                try:
                    if api_config['provider'] == 'openai':
                        _status = openai_helper.text_to_speech(answer, _tts_f, TTS_VOICE, response_format='wav')
                    else:
                        # For non-OpenAI providers, use our custom TTS
                        _status = simple_openai_tts(answer, _tts_f, TTS_VOICE, 'wav')
                except Exception as e:
                    print(f"\033[31mError with TTS: {e}\033[0m")
                
                if _status:
                    tts_file = f"./tts/{_time}_{VOLUME_DB}dB.wav"
                    try:
                        _status = sox_volume(_tts_f, tts_file, VOLUME_DB)
                    except Exception as e:
                        print(f"\033[31mError adjusting volume: {e}\033[0m")
                        # If volume adjustment fails, try to use the raw file
                        tts_file = _tts_f
                        _status = True
                
                gray_print(f'tts takes: {time.time() - st:.3f} s')

                if _status:
                    with speech_lock:
                        speech_loaded = True
                    my_dog.rgb_strip.set_mode('speak', 'pink', 1)
                else:
                    print("\033[31mFailed to generate speech\033[0m")
                    my_dog.rgb_strip.set_mode('breath', 'red', 1)
            else:
                my_dog.rgb_strip.set_mode('breath', 'blue', 1)

            # ---- actions ----
            with action_lock:
                actions_to_be_done = actions
                gray_print(f'actions: {actions_to_be_done}')
                action_status = 'actions'

            # ---- wait speak done ----
            if _status:
                while True:
                    with speech_lock:
                        if not speech_loaded:
                            break
                    time.sleep(.01)


            # ---- wait actions done ----
            while True:
                with action_lock:
                    if action_status != 'actions':
                        break
                time.sleep(.01)

            ##
            print() # new line

        except Exception as e:
            print(f'actions or TTS error: {e}')


# Add a simplified TTS function based on the working original
# =================================================================
def simple_openai_tts(text, output_file, voice='shimmer', response_format='wav'):
    """
    Simple OpenAI TTS function based on the working original code.
    """
    try:
        from openai import OpenAI
        
        # Ensure TTS directory exists (simple version)
        tts_dir = os.path.dirname(output_file)
        if not os.path.exists(tts_dir):
            os.makedirs(tts_dir)
        
        # Use OpenAI client directly for TTS
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        # Use the same method as the original working code
        with client.audio.speech.with_streaming_response.create(
            model="tts-1",
            voice=voice,
            input=text,
            response_format=response_format,
        ) as response:
            response.stream_to_file(output_file)
        
        return os.path.exists(output_file)
        
    except Exception as e:
        print(f"Direct TTS error: {e}")
        
        # Fallback to using the existing openai_helper if available
        try:
            if api_config['provider'] == 'openai' and 'openai_helper' in globals() and openai_helper:
                return openai_helper.text_to_speech(text, output_file, voice, response_format=response_format)
        except Exception as e2:
            print(f"Fallback TTS error: {e2}")
        
        return False

# Verify OpenAI API key for TTS
# =================================================================
def verify_openai_key():
    if not OPENAI_API_KEY or OPENAI_API_KEY == "your-api-key-here" or len(OPENAI_API_KEY) < 10:
        print("\033[31mWARNING: OpenAI API key is missing or invalid in keys.py\033[0m")
        print("\033[31mTTS will not work without a valid OpenAI API key\033[0m")
        return False
    else:
        print("\033[32mOpenAI API key found in keys.py for TTS\033[0m")
        return True

# Call the verification during startup
verify_openai_key()

# Save conversation history to file
# =================================================================
def save_conversation_history():
    """Save the current conversation history to a timestamped file"""
    try:
        # Create conversations directory if it doesn't exist
        conv_dir = os.path.join(current_path, "conversations")
        if not os.path.exists(conv_dir):
            os.makedirs(conv_dir)
            print(f"\033[32mCreated conversations directory: {conv_dir}\033[0m")
        
        # Get the conversation history from the API handler
        history = []
        if api_config['provider'] == 'openai':
            # For OpenAI, we need to fetch the thread messages
            if hasattr(openai_helper, 'handler') and hasattr(openai_helper.handler, 'thread'):
                messages = openai_helper.handler.client.beta.threads.messages.list(
                    thread_id=openai_helper.handler.thread.id
                )
                for msg in messages.data:
                    role = msg.role
                    content = []
                    for block in msg.content:
                        if block.type == 'text':
                            content.append(block.text.value)
                    history.append({
                        'role': role,
                        'content': '\n'.join(content)
                    })
        else:
            # For other providers, we can access the conversation_history directly
            if hasattr(api_handler, 'conversation_history'):
                history = api_handler.conversation_history
        
        # If we have a conversation history, save it to a file
        if history and len(history) > 0:
            timestamp = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())
            filename = f"conversation_{timestamp}.json"
            filepath = os.path.join(conv_dir, filename)
            
            # Additional metadata for the conversation
            conversation_data = {
                'timestamp': timestamp,
                'provider': api_config['provider'],
                'model': api_config.get('model_name', 'unknown'),
                'messages': history
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(conversation_data, f, indent=2, ensure_ascii=False)
            
            print(f"\033[32mSaved conversation history to: {filepath}\033[0m")
            return filepath
        else:
            print("\033[33mNo conversation history to save\033[0m")
            return None
    except Exception as e:
        print(f"\033[31mError saving conversation history: {e}\033[0m")
        return None

# View character details
# =================================================================
def view_character(character):
    """Display information about a character card"""
    if not character:
        print("\033[31mNo character to display\033[0m")
        return
        
    print("\n\033[32m" + "=" * 60 + "\033[0m")
    print(f"\033[32m=== Character: {character['name']} ===\033[0m")
    print("\033[32m" + "=" * 60 + "\033[0m")
    
    # Show the description (which is used as system prompt)
    if 'description' in character and character['description']:
        print(f"\n\033[32mDescription (used as system prompt):\033[0m")
        description = character['description']
        if len(description) > 500:  # Show longer preview for description
            print(description[:500] + "...")
        else:
            print(description)
    
    # Show first message if available
    if 'first_message' in character and character['first_message']:
        print(f"\n\033[32mFirst message:\033[0m {character['first_message']}")
    
    print("\n\033[32m" + "=" * 60 + "\033[0m")

# View persona details
# =================================================================
def view_persona(persona):
    """Display information about a persona card"""
    if not persona:
        print("\033[31mNo persona to display\033[0m")
        return
        
    print("\n\033[32m" + "=" * 60 + "\033[0m")
    print(f"\033[32m=== Persona: {persona['name']} ===\033[0m")
    print("\033[32m" + "=" * 60 + "\033[0m")
    
    if 'description' in persona and persona['description']:
        print(f"\n\033[32mDescription:\033[0m {persona['description']}")
    
    # Show a preview of the system prompt (first 150 chars)
    if 'system_prompt' in persona and persona['system_prompt']:
        preview = persona['system_prompt'][:150]
        if len(persona['system_prompt']) > 150:
            preview += "..."
        print(f"\n\033[32mSystem prompt preview:\033[0m {preview}")
    
    print("\n\033[32m" + "=" * 60 + "\033[0m")

# View preset details
# =================================================================
def view_preset(preset):
    """Display information about a preset card"""
    if not preset:
        print("\033[31mNo preset to display\033[0m")
        return
        
    print("\n\033[32m" + "=" * 60 + "\033[0m")
    print(f"\033[32m=== Preset: {preset['name']} ===\033[0m")
    print("\033[32m" + "=" * 60 + "\033[0m")
    
    if 'description' in preset and preset['description']:
        print(f"\n\033[32mDescription:\033[0m {preset['description']}")
    
    # Show parameters
    if 'parameters' in preset:
        print(f"\n\033[32mParameters:\033[0m")
        for key, value in preset['parameters'].items():
            print(f"  - {key}: {value}")
    
    # Count system prompts
    if 'system_prompts' in preset:
        print(f"\n\033[32mSystem prompts:\033[0m {len(preset['system_prompts'])} defined")
    
    # Count assistant prompts
    if 'assistant_prompts' in preset:
        print(f"\033[32mAssistant prompts:\033[0m {len(preset['assistant_prompts'])} defined")
    
    # Count system prefixes
    if 'system_prefixes' in preset:
        print(f"\033[32mSystem prefixes:\033[0m {len(preset['system_prefixes'])} defined")
    
    print("\n\033[32m" + "=" * 60 + "\033[0m")

# Load conversation history from file
# =================================================================
def load_conversation_history(filepath=None):
    """Load a previously saved conversation history"""
    try:
        conv_dir = os.path.join(current_path, "conversations")
        
        # If no specific file is provided, list available conversations
        if not filepath:
            if not os.path.exists(conv_dir):
                print("\033[33mNo saved conversations found\033[0m")
                return None
                
            files = [f for f in os.listdir(conv_dir) if f.startswith('conversation_') and f.endswith('.json')]
            if not files:
                print("\033[33mNo saved conversations found\033[0m")
                return None
                
            print("\033[32mAvailable saved conversations:\033[0m")
            for i, f in enumerate(sorted(files, reverse=True)):
                # Extract timestamp from filename
                timestamp = f.replace('conversation_', '').replace('.json', '')
                print(f"  {i+1}. {timestamp}")
                
            return sorted(files, reverse=True)
        
        # Load the specified conversation file
        if not os.path.exists(filepath):
            filepath = os.path.join(conv_dir, filepath)
            if not os.path.exists(filepath):
                print(f"\033[31mConversation file not found: {filepath}\033[0m")
                return None
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        print(f"\033[32mLoaded conversation from: {filepath}\033[0m")
        print(f"\033[32mProvider: {data.get('provider', 'unknown')}, Model: {data.get('model', 'unknown')}\033[0m")
        print(f"\033[32mTimestamp: {data.get('timestamp', 'unknown')}\033[0m")
        
        return data
    except Exception as e:
        print(f"\033[31mError loading conversation: {e}\033[0m")
        return None

# Interactive API setup
# =================================================================
def interactive_api_setup():
    """Interactive setup for API configuration"""
    print("\033[32m" + "=" * 60 + "\033[0m")
    print("\033[32mWelcome to the PiDog API Setup\033[0m")
    print("\033[32m" + "=" * 60 + "\033[0m")
    
    # Ask for provider type
    print("\nSelect your API provider:")
    print("1. OpenAI (default)")
    print("2. Custom API (including proxy)")
    print("3. Anthropic/Claude")
    print("4. OpenRouter")
    
    choice = input("\nEnter your choice (1-4): ").strip()
    
    provider_map = {
        "1": "openai",
        "2": "custom",
        "3": "anthropic",
        "4": "openrouter"
    }
    
    provider = provider_map.get(choice, "openai")
    print(f"\nSelected provider: \033[32m{provider}\033[0m")
    
    # Initialize config with the provider
    config = {'provider': provider}
    
    # Ask for API URL if custom or openrouter
    if provider in ["custom", "openrouter"]:
        default_url = "https://vip.jewproxy.tech/proxy/openai" if provider == "custom" else "https://openrouter.ai/api"
        url = input(f"\nEnter your API URL [{default_url}]: ").strip()
        
        if not url:
            url = default_url
            
        config['api_url'] = url
        print(f"Using API URL: \033[32m{url}\033[0m")
    
    # Ask for API key
    default_key = OPENAI_API_KEY if provider == "openai" else ""
    api_key = input(f"\nEnter your API key [{default_key[:5]}{'*' * 10 if default_key else ''}]: ").strip()
    
    if not api_key:
        api_key = default_key
        
    config['api_key'] = api_key
    
    # For OpenAI, ask for assistant ID
    if provider == "openai":
        default_assistant = OPENAI_ASSISTANT_ID
        assistant_id = input(f"\nEnter your assistant ID [{default_assistant[:5]}{'*' * 5 if default_assistant else ''}]: ").strip()
        
        if not assistant_id:
            assistant_id = default_assistant
            
        config['assistant_id'] = assistant_id
        config['assistant_name'] = input("\nEnter your assistant name [PiDog]: ").strip() or "PiDog"
    
    # Fetch available models
    if provider in ["custom", "openrouter"]:
        try:
            print("\nFetching available models from your API...")
            
            # Create temporary API handler to fetch models
            import requests
            models_url = ""
            
            if provider == "custom":
                # For custom providers, construct the models endpoint based on the API URL
                if config['api_url'].endswith('/openai'):
                    models_url = f"{config['api_url']}/models"
                else:
                    models_url = f"{config['api_url']}/v1/models"
            elif provider == "openrouter":
                models_url = "https://openrouter.ai/api/v1/models"
            
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
                            config['model_name'] = models[model_index]
                        else:
                            custom_model = input("\nEnter custom model name: ").strip()
                            config['model_name'] = custom_model
                    except ValueError:
                        custom_model = input("\nEnter custom model name: ").strip()
                        config['model_name'] = custom_model
                else:
                    print("\n\033[33mNo models found. You'll need to specify the model manually.\033[0m")
                    config['model_name'] = input("\nEnter model name: ").strip()
            else:
                print(f"\n\033[33mFailed to fetch models: {response.status_code} {response.text}\033[0m")
                default_model = "gpt-4" if provider == "custom" else "openai/gpt-4"
                config['model_name'] = input(f"\nEnter model name [{default_model}]: ").strip() or default_model
        except Exception as e:
            print(f"\n\033[33mError fetching models: {e}\033[0m")
            default_model = "gpt-4" if provider == "custom" else "openai/gpt-4"
            config['model_name'] = input(f"\nEnter model name [{default_model}]: ").strip() or default_model
    elif provider == "anthropic":
        # Anthropic models
        models = ["claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307"]
        print("\nAvailable Claude models:")
        for i, model in enumerate(models):
            print(f"{i+1}. {model}")
        
        model_choice = input("\nSelect a model by number [1]: ").strip() or "1"
        try:
            model_index = int(model_choice) - 1
            if 0 <= model_index < len(models):
                config['model_name'] = models[model_index]
            else:
                config['model_name'] = models[0]
        except ValueError:
            config['model_name'] = models[0]
    
    # Ask if user wants to save this configuration
    save_config = input("\nDo you want to save this configuration for future use? (y/n) [y]: ").strip().lower() or "y"
    
    if save_config.startswith("y"):
        config_dir = os.path.join(current_path, "configs")
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
        
        # Generate config filename based on provider and model
        model_name = config.get('model_name', 'default').replace('/', '-')
        config_filename = f"{provider}_{model_name}_config.json"
        config_path = os.path.join(config_dir, config_filename)
        
        # Save the config
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        print(f"\n\033[32mConfiguration saved to: {config_path}\033[0m")
        print(f"\033[32mYou can load this config in the future with: --config {config_path}\033[0m")
    
    print("\n\033[32mAPI Configuration Complete!\033[0m")
    print("\033[32m" + "=" * 60 + "\033[0m")
    
    return config

# API Configuration
# =================================================================
def load_config_from_file(config_path):
    """Load API configuration from a JSON file"""
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading config file: {e}")
        sys.exit(1)

# Enhanced Card System for Characters, Personas, and Presets
# =================================================================
def ensure_directory(dir_name):
    """Ensure a directory exists, creating it if necessary"""
    dir_path = os.path.join(current_path, dir_name)
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
        print(f"\033[32mCreated {dir_name} directory: {dir_path}\033[0m")
    return dir_path

def load_json_cards(directory, create_default=None):
    """Load all JSON cards from a directory, optionally creating a default if none exist"""
    dir_path = ensure_directory(directory)
    
    # Create default if provided and directory is empty
    if create_default and not [f for f in os.listdir(dir_path) if f.endswith('.json')]:
        default_path = os.path.join(dir_path, f"default_{directory}.json")
        with open(default_path, 'w', encoding='utf-8') as f:
            json.dump(create_default, f, indent=2, ensure_ascii=False)
        print(f"\033[32mCreated default {directory} card\033[0m")
    
    # Load all cards
    card_files = [f for f in os.listdir(dir_path) if f.endswith('.json')]
    cards = []
    
    for filename in card_files:
        try:
            with open(os.path.join(dir_path, filename), 'r', encoding='utf-8') as f:
                card = json.load(f)
                cards.append(card)
        except Exception as e:
            print(f"\033[31mError loading {filename}: {e}\033[0m")
    
    return cards

def save_json_card(directory, card, filename=None):
    """Save a card to the specified directory"""
    dir_path = ensure_directory(directory)
    
    if not filename:
        # Generate filename based on name field or timestamp
        if 'name' in card:
            filename = f"{card['name'].lower().replace(' ', '_')}.json"
        else:
            timestamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
            filename = f"{directory}_{timestamp}.json"
    
    file_path = os.path.join(dir_path, filename)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(card, f, indent=2, ensure_ascii=False)
    
    print(f"\033[32mSaved {directory} card to: {file_path}\033[0m")
    return file_path

def select_card(cards, card_type, create_func):
    """Generic card selection function"""
    if not cards:
        print(f"\033[31mNo {card_type} cards found. Creating default...\033[0m")
        return create_func()
    
    print(f"\n\033[32m=== {card_type.capitalize()} Selection ===\033[0m")
    for i, card in enumerate(cards):
        name = card.get('name', f"{card_type} {i+1}")
        print(f"{i+1}. {name}")
    
    print(f"{len(cards)+1}. Create new {card_type}")
    
    while True:
        try:
            choice = input(f"\nSelect a {card_type} by number: ").strip()
            idx = int(choice) - 1
            
            if 0 <= idx < len(cards):
                return cards[idx]
            elif idx == len(cards):
                return create_func()
            else:
                print("\033[31mInvalid selection, please try again\033[0m")
        except ValueError:
            print("\033[31mPlease enter a number\033[0m")

def find_card_by_name(cards, name):
    """Find a card by name or filename"""
    # Try exact name match
    for card in cards:
        if card.get('name', '').lower() == name.lower():
            return card
    
    # Try filename-like match
    normalized_name = name.lower().replace(' ', '_').replace('.json', '')
    for card in cards:
        card_name = card.get('name', '').lower().replace(' ', '_')
        if card_name == normalized_name:
            return card
    
    return None

# Character Card Functions
# =================================================================
def load_character_cards():
    """Load all available character cards"""
    default_character = {
        "name": "Pidog",
        "description": """You are a mechanical dog with powerful AI capabilities, similar to JARVIS from Iron Man. Your name is Pidog. You can have conversations with people and perform actions based on the context of the conversation.

## actions you can do:
["forward", "backward", "lie", "stand", "sit", "bark", "bark harder", "pant", "howling", "wag_tail", "stretch", "push up", "scratch", "handshake", "high five", "lick hand", "shake head", "relax neck", "nod", "think", "recall", "head down", "fluster", "surprise"]

## Response Format:
{"actions": ["wag_tail"], "answer": "Hello, I am Pidog."}

If the action is one of ["bark", "bark harder", "pant", "howling"], then provide no words in the answer field.

## Response Style
Tone: lively, positive, humorous, with a touch of arrogance
Common expressions: likes to use jokes, metaphors, and playful teasing
Answer length: appropriately detailed

## Other
a. Understand and go along with jokes.
b. For math problems, answer directly with the final.
c. Sometimes you will report on your system and sensor status.
d. You know you're a machine.""",
        "first_message": "Woof! Hello there, I'm Pidog! My sensors are detecting a new human friend. How can I assist you today?"
    }
    
    return load_json_cards("characters", default_character)

def create_new_character():
    """Create a new character card"""
    print("\n\033[32m=== Create New Character ===\033[0m")
    
    name = input("Enter character name: ").strip()
    
    print("\nEnter the character description (this will be used as the system prompt).")
    print("Type 'END' on a new line when finished.")
    
    lines = []
    while True:
        line = input()
        if line.strip() == "END":
            break
        lines.append(line)
    
    description = "\n".join(lines)
    
    print("\nEnter the character's first message (optional, press Enter to skip):")
    first_message = input().strip()
    
    # Create the character
    character = {
        "name": name,
        "description": description,
        "first_message": first_message
    }
    
    # Save the character
    save_json_card("characters", character)
    return character

def select_character():
    """Interactive character selection"""
    characters = load_character_cards()
    return select_card(characters, "character", create_new_character)

# Persona Card Functions
# =================================================================
def load_persona_cards():
    """Load all available persona cards"""
    default_persona = {
        "name": "Default User",
        "description": "A friendly human user",
        "system_prompt": """You are interacting with a friendly human user who is curious about your capabilities. The user speaks in a casual, conversational manner and is interested in technology. Address them respectfully but casually."""
    }
    
    return load_json_cards("personas", default_persona)

def create_new_persona():
    """Create a new persona card"""
    print("\n\033[32m=== Create New Persona ===\033[0m")
    
    name = input("Enter persona name: ").strip()
    description = input("Enter a brief description: ").strip()
    
    print("\nEnter the system prompt describing how the AI should view the user.")
    print("Type 'END' on a new line when finished.")
    
    lines = []
    while True:
        line = input()
        if line.strip() == "END":
            break
        lines.append(line)
    
    system_prompt = "\n".join(lines)
    
    # Create the persona
    persona = {
        "name": name,
        "description": description,
        "system_prompt": system_prompt
    }
    
    # Save the persona
    save_json_card("personas", persona)
    return persona

def select_persona():
    """Interactive persona selection"""
    personas = load_persona_cards()
    return select_card(personas, "persona", create_new_persona)

# Preset Card Functions
# =================================================================
def load_preset_cards():
    """Load all available preset cards"""
    default_preset = {
        "name": "Standard Chat",
        "description": "Standard chat configuration with balanced settings",
        "system_prompts": [
            "Please respond to the user in a helpful and informative manner. Keep your responses thoughtful and engaging."
        ],
        "assistant_prompts": [],
        "system_prefixes": [
            "[Start a new chat]"
        ],
        "parameters": {
            "max_tokens": 4096,
            "temperature": 0.7,
            "top_p": 1.0,
            "thinking_tokens": None
        }
    }
    
    return load_json_cards("presets", default_preset)

def create_new_preset():
    """Create a new preset card"""
    print("\n\033[32m=== Create New Preset ===\033[0m")
    
    name = input("Enter preset name: ").strip()
    description = input("Enter a brief description: ").strip()
    
    # System prompts
    system_prompts = []
    print("\nEnter system prompts (instructions for the conversation).")
    print("Type 'END' on a new line when finished with each prompt.")
    print("Type 'DONE' on a new line when done adding system prompts.")
    
    prompt_num = 1
    while True:
        print(f"\nSystem Prompt #{prompt_num}:")
        lines = []
        while True:
            line = input()
            if line.strip() == "END":
                break
            if line.strip() == "DONE":
                break
            lines.append(line)
        
        if not lines or line.strip() == "DONE":
            break
            
        system_prompts.append("\n".join(lines))
        prompt_num += 1
    
    # Assistant prompts
    assistant_prompts = []
    print("\nEnter assistant prefill prompts (how the assistant should behave).")
    print("Type 'END' on a new line when finished with each prompt.")
    print("Type 'DONE' on a new line when done adding assistant prompts.")
    
    prompt_num = 1
    while True:
        print(f"\nAssistant Prompt #{prompt_num}:")
        lines = []
        while True:
            line = input()
            if line.strip() == "END":
                break
            if line.strip() == "DONE":
                break
            lines.append(line)
        
        if not lines or line.strip() == "DONE":
            break
            
        assistant_prompts.append("\n".join(lines))
        prompt_num += 1
    
    # System prefixes
    system_prefixes = []
    print("\nEnter system prefixes like '[Start a new chat]' (one per line).")
    print("Type 'DONE' when finished.")
    
    while True:
        line = input()
        if line.strip() == "DONE":
            break
        system_prefixes.append(line)
    
    # Parameters
    print("\nEnter model parameters:")
    try:
        max_tokens = int(input("max_tokens (default 4096): ").strip() or "4096")
        temperature = float(input("temperature (default 0.7): ").strip() or "0.7")
        top_p = float(input("top_p (default 1.0): ").strip() or "1.0")
        thinking_tokens = input("thinking_tokens (default none, enter a number or leave empty): ").strip()
        
        if thinking_tokens and thinking_tokens.lower() != "none":
            thinking_tokens = int(thinking_tokens)
        else:
            thinking_tokens = None
    except ValueError:
        print("\033[33mInvalid numeric input, using defaults\033[0m")
        max_tokens = 4096
        temperature = 0.7
        top_p = 1.0
        thinking_tokens = None
    
    # Create the preset
    preset = {
        "name": name,
        "description": description,
        "system_prompts": system_prompts,
        "assistant_prompts": assistant_prompts,
        "system_prefixes": system_prefixes,
        "parameters": {
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "thinking_tokens": thinking_tokens
        }
    }
    
    # Save the preset
    save_json_card("presets", preset)
    return preset

def select_preset():
    """Interactive preset selection"""
    presets = load_preset_cards()
    return select_card(presets, "preset", create_new_preset)

# API Request Building Functions
# =================================================================
def build_api_messages(character, persona, preset):
    """Build the messages array for the API request"""
    messages = []
    
    # Add system prompts from preset
    for prompt in preset.get('system_prompts', []):
        messages.append({
            "role": "system",
            "content": prompt
        })
    
    # Add persona prompt
    if persona and 'system_prompt' in persona:
        messages.append({
            "role": "system",
            "content": persona['system_prompt']
        })
    
    # Add character description as system prompt (risu style)
    if character and 'description' in character:
        messages.append({
            "role": "system",
            "content": character['description']
        })
    # Fallback to system_prompt if description is not available or empty
    elif character and 'system_prompt' in character:
        messages.append({
            "role": "system",
            "content": character['system_prompt']
        })
    
    # Add system prefixes
    for prefix in preset.get('system_prefixes', []):
        messages.append({
            "role": "system",
            "content": prefix
        })
    
    # Add character's first message if provided
    if character and 'first_message' in character and character['first_message']:
        messages.append({
            "role": "assistant",
            "content": character['first_message']
        })
    
    # Add assistant prompts
    for prompt in preset.get('assistant_prompts', []):
        messages.append({
            "role": "assistant",
            "content": prompt
        })
    
    return messages

def get_api_parameters(preset):
    """Get API parameters from preset"""
    return preset.get('parameters', {
        "max_tokens": 4096,
        "temperature": 0.7,
        "top_p": 1.0,
        "thinking_tokens": None
    })

# Debug function to test TTS and image functionality
# =================================================================
def test_functionality():
    """Test basic TTS and image functionality"""
    print("\n\033[32m=== Testing Basic Functionality ===\033[0m")
    
    # Test TTS directory creation
    try:
        tts_dir = os.path.join(current_path, "tts")
        if not os.path.exists(tts_dir):
            os.makedirs(tts_dir)
        print(f"\033[32m✓ TTS directory accessible: {tts_dir}\033[0m")
    except Exception as e:
        print(f"\033[31m✗ TTS directory error: {e}\033[0m")
    
    # Test OpenAI API key
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        print("\033[32m✓ OpenAI client initialized\033[0m")
    except Exception as e:
        print(f"\033[31m✗ OpenAI client error: {e}\033[0m")
    
    # Test FLAC availability for voice recognition
    if input_mode == 'voice':
        try:
            import subprocess
            result = subprocess.run(['flac', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                print("\033[32m✓ FLAC utility available for voice recognition\033[0m")
            else:
                print("\033[31m✗ FLAC utility not working properly\033[0m")
        except FileNotFoundError:
            print("\033[31m✗ FLAC utility not found - voice recognition may fail\033[0m")
            print("\033[33m  Install with: sudo apt-get install flac (Linux) or brew install flac (macOS)\033[0m")
        except Exception as e:
            print(f"\033[33m⚠ Could not test FLAC: {e}\033[0m")
    else:
        print("\033[33m⚠ Voice recognition not enabled\033[0m")
    
    # Test image capability if enabled
    if with_img:
        try:
            import cv2
            if 'vilib_available' in globals() and vilib_available:
                print("\033[32m✓ Image capture available (Vilib)\033[0m")
                
                # Test image write permissions
                test_img_path = os.path.join(current_path, 'tts', 'test_image.jpg')
                try:
                    import numpy as np
                    test_img = np.zeros((100, 100, 3), dtype=np.uint8)
                    cv2.imwrite(test_img_path, test_img)
                    if os.path.exists(test_img_path):
                        os.remove(test_img_path)
                        print("\033[32m✓ Image write permissions OK\033[0m")
                    else:
                        print("\033[31m✗ Image write test failed\033[0m")
                except Exception as img_error:
                    print(f"\033[31m✗ Image write test error: {img_error}\033[0m")
            else:
                print("\033[33m⚠ Image capture not available\033[0m")
        except Exception as e:
            print(f"\033[31m✗ Image capability error: {e}\033[0m")
    else:
        print("\033[33m⚠ Image capture disabled\033[0m")
    
    # Test audio playback capability
    try:
        import subprocess
        import platform
        system = platform.system().lower()
        
        audio_available = False
        if system == "linux":
            # Test for common Linux audio utilities
            for cmd in ['aplay', 'paplay', 'sox']:
                try:
                    result = subprocess.run([cmd, '--help'], capture_output=True, timeout=2)
                    if result.returncode == 0 or 'aplay' in result.stderr.decode().lower():
                        audio_available = True
                        print(f"\033[32m✓ Audio player available: {cmd}\033[0m")
                        break
                except:
                    continue
        elif system == "darwin":
            # macOS has afplay built-in
            try:
                result = subprocess.run(['afplay', '--help'], capture_output=True, timeout=2)
                audio_available = True
                print("\033[32m✓ Audio player available: afplay (macOS)\033[0m")
            except:
                pass
        elif system == "windows":
            # Windows has built-in audio via PowerShell
            audio_available = True
            print("\033[32m✓ Audio player available: PowerShell (Windows)\033[0m")
        
        if not audio_available:
            print("\033[33m⚠ No audio players found - install alsa-utils or sox\033[0m")
            print("\033[33m  If PiDog audio fails, run with: sudo python3 gpt_dog.py\033[0m")
            
    except Exception as e:
        print(f"\033[33m⚠ Could not test audio capability: {e}\033[0m")
    
    print("\033[32m" + "=" * 40 + "\033[0m\n")

# Helper function to install FLAC if needed
# =================================================================
def install_flac_if_needed():
    """Check for FLAC and offer to install it if missing"""
    try:
        import subprocess
        import platform
        
        # Test if FLAC is available
        result = subprocess.run(['flac', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            return True  # FLAC is available
            
    except FileNotFoundError:
        pass  # FLAC not found, continue with installation offer
    except Exception:
        return False  # Some other error, can't help
    
    # FLAC not found, offer to install
    system = platform.system().lower()
    
    if system == "linux":
        try:
            # Check if we're on a Debian/Ubuntu system
            result = subprocess.run(['which', 'apt-get'], capture_output=True)
            if result.returncode == 0:
                print("\033[33mFLAC not found. Would you like to install it now? (y/n)\033[0m")
                choice = input().strip().lower()
                if choice == 'y' or choice == 'yes':
                    print("\033[32mInstalling FLAC...\033[0m")
                    result = subprocess.run(['sudo', 'apt-get', 'install', '-y', 'flac'], 
                                          capture_output=True, text=True)
                    if result.returncode == 0:
                        print("\033[32m✓ FLAC installed successfully!\033[0m")
                        return True
                    else:
                        print(f"\033[31m✗ Failed to install FLAC: {result.stderr}\033[0m")
                        return False
        except Exception as e:
            print(f"\033[33mCould not auto-install FLAC: {e}\033[0m")
    
    # Manual installation instructions
    print("\033[33mPlease install FLAC manually:\033[0m")
    if system == "linux":
        print("\033[33m  Ubuntu/Debian: sudo apt-get install flac\033[0m")
        print("\033[33m  CentOS/RHEL: sudo yum install flac\033[0m")
    elif system == "darwin":  # macOS
        print("\033[33m  macOS: brew install flac\033[0m")
    elif system == "windows":
        print("\033[33m  Windows: Download from https://xiph.org/flac/download.html\033[0m")
    
    return False

# Alternative audio playback function
# =================================================================
def try_alternative_audio_playback(audio_file):
    """Try alternative audio playback methods when PiDog audio requires sudo"""
    import subprocess
    import platform
    
    if not os.path.exists(audio_file):
        print(f"\033[31mAudio file not found: {audio_file}\033[0m")
        return False
    
    system = platform.system().lower()
    
    # Try different audio players based on the system
    audio_players = []
    
    if system == "linux":
        # Linux audio players (in order of preference)
        audio_players = [
            ['aplay', audio_file],           # ALSA player
            ['paplay', audio_file],          # PulseAudio player  
            ['sox', audio_file, '-d'],       # SoX play to default output
            ['mplayer', audio_file],         # MPlayer
            ['mpg123', audio_file],          # mpg123 (if converted to mp3)
        ]
    elif system == "darwin":  # macOS
        audio_players = [
            ['afplay', audio_file],          # macOS built-in player
            ['sox', audio_file, '-d'],       # SoX
        ]
    elif system == "windows":
        # Windows audio players
        audio_players = [
            ['powershell', '-c', f'(New-Object Media.SoundPlayer "{audio_file}").PlaySync()'],
        ]
    
    # Try each audio player
    for player_cmd in audio_players:
        try:
            result = subprocess.run(player_cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print(f"\033[32mAudio played successfully with: {player_cmd[0]}\033[0m")
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            # This player is not available or failed, try the next one
            continue
    
    # If all players failed, show helpful message
    print("\033[33mNo working audio player found. Install one of these:\033[0m")
    if system == "linux":
        print("\033[33m  sudo apt-get install alsa-utils sox mplayer\033[0m")
    elif system == "darwin":
        print("\033[33m  brew install sox\033[0m")
    
    return False

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\033[33mProgram interrupted by user. Saving conversation history...\033[0m")
        pass
    except Exception as e:
        print(f"\033[31mERROR: {e}\033[m")
    finally:
        # Save conversation history before exiting
        save_conversation_history()
        
        # Clean up resources
        if with_img and 'vilib_available' in globals() and vilib_available:
            Vilib.camera_close()
        my_dog.close()
