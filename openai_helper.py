from openai import OpenAI
import time
import shutil
import os
import requests
import json
from typing import Optional, Dict, Any, List, Union

# utils
# =================================================================
def chat_print(label, message):
    width = shutil.get_terminal_size().columns
    msg_len = len(message)
    line_len = width - 27

    # --- normal print ---
    print(f'{time.time():.3f} {label:>6} >>> {message}')
    return

    # --- table mode ---
    if width < 38 or msg_len <= line_len:
        print(f'{time.time():.3f} {label:>6} >>> {message}')
    else:
        texts = []

        # words = message.split()
        # print(words)
        # current_line = ""
        # for word in words:
        #     if len(current_line) + len(word) + 1 <= line_len:
        #         current_line += word + " "
        #     else:
        #         texts.append(current_line)
        #         current_line = ""

        # if current_line:
        #     texts.append(current_line)

        for i in range(0, len(message), line_len):
            texts.append(message[i:i+line_len])

        for i, text in enumerate(texts):
            if i == 0:
                print(f'{time.time():.3f} {label:>6} >>> {text}')
            else:
                print(f'{"":>26} {text}')

# API Handlers
# =================================================================
class APIHandler:
    """Base class for API handlers"""
    
    def __init__(self, api_key: str, api_url: Optional[str] = None, timeout: int = 30):
        self.api_key = api_key
        self.api_url = api_url
        self.timeout = timeout
        
    def stt(self, audio, language='en'):
        """Speech to text conversion - implement in subclasses"""
        pass
        
    def dialogue(self, msg):
        """Process dialogue messages - implement in subclasses"""
        pass
        
    def dialogue_with_img(self, msg, img_path):
        """Process dialogue with image - implement in subclasses"""
        pass
        
    def text_to_speech(self, text, output_file, voice='alloy', response_format="mp3", speed=1):
        """Text to speech conversion - implement in subclasses"""
        pass


class OpenAIHandler(APIHandler):
    """Handler for OpenAI API"""
    
    STT_OUT = "stt_output.wav"
    TTS_OUTPUT_FILE = 'tts_output.mp3'
    
    def __init__(self, api_key, assistant_id, assistant_name, api_url=None, timeout=30):
        super().__init__(api_key, api_url, timeout)
        self.assistant_id = assistant_id
        self.assistant_name = assistant_name
        
        # Initialize client with base URL if provided
        client_kwargs = {"api_key": api_key, "timeout": timeout}
        if api_url:
            client_kwargs["base_url"] = api_url
            
        self.client = OpenAI(**client_kwargs)
        self.thread = self.client.beta.threads.create()
        self.run = self.client.beta.threads.runs.create_and_poll(
            thread_id=self.thread.id,
            assistant_id=assistant_id,
        )

    def stt(self, audio, language='en'):
        try:
            import wave
            from io import BytesIO

            wav_data = BytesIO(audio.get_wav_data())
            wav_data.name = self.STT_OUT

            transcript = self.client.audio.transcriptions.create(
                model="whisper-1", 
                file=wav_data,
                language=language,
                prompt="this is the conversation between me and a robot"
            )

            return transcript.text
        except Exception as e:
            print(f"stt err:{e}")
            return False

    def speech_recognition_stt(self, recognizer, audio):
        import speech_recognition as sr

        try:
            return recognizer.recognize_whisper_api(audio, api_key=self.api_key)
        except sr.RequestError as e:
            print(f"Could not request results from Whisper API; {e}")
            return False

    def dialogue(self, msg):
        chat_print("user", msg)
        message = self.client.beta.threads.messages.create(
            thread_id=self.thread.id,
            role="user",
            content=msg
            )
        run = self.client.beta.threads.runs.create_and_poll(
            thread_id=self.thread.id,
            assistant_id=self.assistant_id,
        )
        if run.status == 'completed': 
            messages = self.client.beta.threads.messages.list(
                thread_id=self.thread.id
            )

            for message in messages.data:
                if message.role == 'assistant':
                    for block in message.content:
                        if block.type == 'text':
                            value = block.text.value
                            chat_print(self.assistant_name, value)
                            try:
                                value = eval(value) # convert to dict
                                return value
                            except Exception as e:
                                return str(value)
                break # only last reply
        else:
            print(run.status)


    def dialogue_with_img(self, msg, img_path):
        chat_print("user", msg)

        img_file = self.client.files.create(
                    file=open(img_path, "rb"),
                    purpose="vision"
                )

        message =  self.client.beta.threads.messages.create(
            thread_id= self.thread.id,
            role="user",
            content= [
                {
                    "type": "text",
                    "text": msg
                },
                {
                    "type": "image_file",
                    "image_file": {"file_id": img_file.id}
                }
            ],
            )
        run = self.client.beta.threads.runs.create_and_poll(
            thread_id=self.thread.id,
            assistant_id=self.assistant_id,
        )
        if run.status == 'completed': 
            messages = self.client.beta.threads.messages.list(
                thread_id=self.thread.id
            )

            for message in messages.data:
                if message.role == 'assistant':
                    for block in message.content:
                        if block.type == 'text':
                            value = block.text.value
                            chat_print(self.assistant_name, value)
                            try:
                                value = eval(value) # convert to dict
                                return value
                            except Exception as e:
                                return str(value)
                break # only last reply
        else:
            print(run.status)


    def text_to_speech(self, text, output_file, voice='alloy', response_format="mp3", speed=1):
        '''
        voice: alloy, echo, fable, onyx, nova, and shimmer
        '''
        try:
            # check dir
            dir = os.path.dirname(output_file)
            if not os.path.exists(dir):
                os.mkdir(dir)
            elif not os.path.isdir(dir):
                raise FileExistsError(f"\'{dir}\' is not a directory")

            # tts
            with self.client.audio.speech.with_streaming_response.create(
                model="tts-1",
                voice=voice,
                input=text,
                response_format=response_format,
                speed=speed,
            ) as response:
                response.stream_to_file(output_file)

            return True
        except Exception as e:
            print(f'tts err: {e}')
            return False


class AnthropicHandler(APIHandler):
    """Handler for Anthropic/Claude API"""
    
    def __init__(self, api_key, model_name="claude-3-opus-20240229", api_url=None, timeout=30):
        super().__init__(api_key, api_url, timeout)
        self.model_name = model_name
        self.base_url = api_url or "https://api.anthropic.com"
        self.conversation_history = []
        
    def _make_request(self, endpoint, payload, headers=None):
        """Helper method to make API requests"""
        url = f"{self.base_url}/{endpoint}"
        _headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        if headers:
            _headers.update(headers)
            
        response = requests.post(url, json=payload, headers=_headers, timeout=self.timeout)
        response.raise_for_status()
        return response.json()
    
    def dialogue(self, msg):
        chat_print("user", msg)
        
        # Add user message to history
        self.conversation_history.append({"role": "user", "content": msg})
        
        # Prepare the payload for Claude API
        payload = {
            "model": self.model_name,
            "messages": self.conversation_history,
            "max_tokens": 1024
        }
        
        try:
            response = self._make_request("v1/messages", payload)
            assistant_msg = response.get("content", [{}])[0].get("text", "")
            
            # Add assistant response to history
            self.conversation_history.append({"role": "assistant", "content": assistant_msg})
            
            chat_print("Claude", assistant_msg)
            
            # Try to convert to dict if possible
            try:
                result = eval(assistant_msg)
                return result
            except:
                return assistant_msg
                
        except Exception as e:
            print(f"Claude API error: {e}")
            return str(e)
    
    def dialogue_with_img(self, msg, img_path):
        chat_print("user", msg)
        
        # Encode image to base64
        import base64
        with open(img_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')
        
        # Create message with text and image
        content = [
            {"type": "text", "text": msg},
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": base64_image
                }
            }
        ]
        
        # Add to conversation history
        self.conversation_history.append({"role": "user", "content": content})
        
        # Prepare the payload
        payload = {
            "model": self.model_name,
            "messages": self.conversation_history,
            "max_tokens": 1024
        }
        
        # LOG THE FULL REQUEST WITH IMAGE
        print("\033[35m" + "=" * 60 + "\033[0m")
        print("\033[35m🖼️ FULL API REQUEST DEBUG (WITH IMAGE)\033[0m")
        print("\033[35m" + "=" * 60 + "\033[0m")
        print(f"\033[35mURL: {self.base_url}/v1/messages\033[0m")
        print(f"\033[35mModel: {self.model_name}\033[0m")
        print(f"\033[35mTotal messages: {len(self.conversation_history)}\033[0m")
        print(f"\033[35mImage file: {img_path}\033[0m")
        print(f"\033[35mImage size: {len(base64_image)} chars (base64)\033[0m")
        print("\033[35m" + "-" * 60 + "\033[0m")
        
        # Log each message with index and details
        for i, message in enumerate(self.conversation_history):
            print(f"\033[35mMessage {i}:\033[0m")
            print(f"  Role: {message['role']}")
            content = message['content']
            if isinstance(content, str):
                print(f"  Content (string): {content[:100]}{'...' if len(content) > 100 else ''}")
            elif isinstance(content, list):
                print(f"  Content (list): {len(content)} items")
                for j, item in enumerate(content):
                    if item.get('type') == 'image':
                        print(f"    Item {j}: image - [BASE64 IMAGE DATA TRUNCATED]")
                    else:
                        print(f"    Item {j}: {type(item)} - {str(item)[:50]}{'...' if len(str(item)) > 50 else ''}")
            else:
                print(f"  Content (other): {type(content)} - {str(content)[:100]}{'...' if len(str(content)) > 100 else ''}")
            print()
        
        print("\033[35m" + "-" * 60 + "\033[0m")
        print("\033[35mPayload structure (image data truncated):\033[0m")
        
        # Create a copy of payload with truncated image data for logging
        import json
        import copy
        log_payload = copy.deepcopy(payload)
        for message in log_payload['messages']:
            if isinstance(message['content'], list):
                for item in message['content']:
                    if item.get('type') == 'image':
                        item['source']['data'] = item['source']['data'][:100] + "...[TRUNCATED]"
        
        print(json.dumps(log_payload, indent=2, ensure_ascii=False))
        print("\033[35m" + "=" * 60 + "\033[0m")
        
        try:
            response = self._make_request("v1/messages", payload)
            assistant_msg = response.get("content", [{}])[0].get("text", "")
            
            # Add assistant response to history
            self.conversation_history.append({"role": "assistant", "content": assistant_msg})
            
            chat_print("Claude", assistant_msg)
            
            # Try to convert to dict if possible
            try:
                result = eval(assistant_msg)
                return result
            except:
                return assistant_msg
                
        except Exception as e:
            print(f"Claude API error: {e}")
            return str(e)
    
    # Note: Anthropic doesn't provide STT or TTS services directly, so these would require integration with other services
    def stt(self, audio, language='en'):
        print("STT not supported directly by Anthropic API")
        return False
        
    def text_to_speech(self, text, output_file, voice='alloy', response_format="mp3", speed=1):
        print("TTS not supported directly by Anthropic API")
        return False


class OpenRouterHandler(APIHandler):
    """Handler for OpenRouter API"""
    
    def __init__(self, api_key, model_name="anthropic/claude-3-opus", api_url=None, timeout=30):
        super().__init__(api_key, api_url, timeout)
        self.model_name = model_name
        self.base_url = api_url or "https://openrouter.ai/api"
        self.conversation_history = []
        
    def _make_request(self, endpoint, payload, headers=None):
        """Helper method to make API requests"""
        url = f"{self.base_url}/{endpoint}"
        _headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://pidog.example.com"
        }
        if headers:
            _headers.update(headers)
            
        response = requests.post(url, json=payload, headers=_headers, timeout=self.timeout)
        response.raise_for_status()
        return response.json()
    
    def dialogue(self, msg):
        chat_print("user", msg)
        
        # Add user message to history
        self.conversation_history.append({"role": "user", "content": msg})
        
        # Prepare the payload for OpenRouter API (OpenAI-compatible format)
        payload = {
            "model": self.model_name,
            "messages": self.conversation_history,
            "max_tokens": 1024,
            "allow_fallbacks": True
        }
        
        try:
            response = self._make_request("v1/chat/completions", payload)
            assistant_msg = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            # Add assistant response to history
            self.conversation_history.append({"role": "assistant", "content": assistant_msg})
            
            chat_print("Router", assistant_msg)
            
            # Try to convert to dict if possible
            try:
                result = eval(assistant_msg)
                return result
            except:
                return assistant_msg
                
        except Exception as e:
            print(f"OpenRouter API error: {e}")
            return str(e)
    
    def dialogue_with_img(self, msg, img_path):
        chat_print("user", msg)
        
        # Encode image to base64
        import base64
        with open(img_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')
        
        # Format dependent on model type
        user_message = {
            "role": "user",
            "content": [
                {"type": "text", "text": msg},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
            ]
        }
        
        # Add to conversation history
        self.conversation_history.append(user_message)
        
        # Prepare the payload
        payload = {
            "model": self.model_name,
            "messages": self.conversation_history,
            "max_tokens": 1024,
            "allow_fallbacks": True
        }
        
        # LOG THE FULL REQUEST WITH IMAGE
        print("\033[35m" + "=" * 60 + "\033[0m")
        print("\033[35m🖼️ FULL API REQUEST DEBUG (WITH IMAGE)\033[0m")
        print("\033[35m" + "=" * 60 + "\033[0m")
        print(f"\033[35mURL: {self.base_url}/v1/chat/completions\033[0m")
        print(f"\033[35mModel: {self.model_name}\033[0m")
        print(f"\033[35mTotal messages: {len(self.conversation_history)}\033[0m")
        print(f"\033[35mImage file: {img_path}\033[0m")
        print(f"\033[35mImage size: {len(base64_image)} chars (base64)\033[0m")
        print("\033[35m" + "-" * 60 + "\033[0m")
        
        # Log each message with index and details
        for i, message in enumerate(self.conversation_history):
            print(f"\033[35mMessage {i}:\033[0m")
            print(f"  Role: {message['role']}")
            content = message['content']
            if isinstance(content, str):
                print(f"  Content (string): {content[:100]}{'...' if len(content) > 100 else ''}")
            elif isinstance(content, list):
                print(f"  Content (list): {len(content)} items")
                for j, item in enumerate(content):
                    if item.get('type') == 'image_url':
                        print(f"    Item {j}: image_url - [BASE64 IMAGE DATA TRUNCATED]")
                    else:
                        print(f"    Item {j}: {type(item)} - {str(item)[:50]}{'...' if len(str(item)) > 50 else ''}")
            else:
                print(f"  Content (other): {type(content)} - {str(content)[:100]}{'...' if len(str(content)) > 100 else ''}")
            print()
        
        print("\033[35m" + "-" * 60 + "\033[0m")
        print("\033[35mPayload structure (image data truncated):\033[0m")
        
        # Create a copy of payload with truncated image data for logging
        import json
        import copy
        log_payload = copy.deepcopy(payload)
        for message in log_payload['messages']:
            if isinstance(message['content'], list):
                for item in message['content']:
                    if item.get('type') == 'image_url':
                        item['image_url']['url'] = item['image_url']['url'][:100] + "...[TRUNCATED]"
        
        print(json.dumps(log_payload, indent=2, ensure_ascii=False))
        print("\033[35m" + "=" * 60 + "\033[0m")
        
        try:
            response = self._make_request("v1/chat/completions", payload)
            assistant_msg = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            # Add assistant response to history
            self.conversation_history.append({"role": "assistant", "content": assistant_msg})
            
            chat_print("Router", assistant_msg)
            
            # Try to convert to dict if possible
            try:
                result = eval(assistant_msg)
                return result
            except:
                return assistant_msg
                
        except Exception as e:
            print(f"OpenRouter API error: {e}")
            return str(e)
    
    # Note: OpenRouter doesn't provide STT or TTS services directly
    def stt(self, audio, language='en'):
        print("STT not supported directly by OpenRouter API")
        return False
        
    def text_to_speech(self, text, output_file, voice='alloy', response_format="mp3", speed=1):
        print("TTS not supported directly by OpenRouter API")
        return False


class CustomAPIHandler(APIHandler):
    """Handler for Custom OpenAI-compatible API endpoints"""
    
    def __init__(self, api_key, model_name, api_url, timeout=30):
        super().__init__(api_key, api_url, timeout)
        self.model_name = model_name
        self.conversation_history = []
        
        # Fix the API URL format for proxies if needed
        if api_url.endswith('/openai'):
            self.api_url = api_url  # The endpoint will be appended later
        elif '/openai/chat/completions' in api_url:
            # URL already includes the endpoint
            self.api_url = api_url.split('/chat/completions')[0]  # Use base URL
            
        print(f"CustomAPIHandler initialized with URL: {self.api_url}, model: {model_name}")
        
    def _make_request(self, endpoint, payload, headers=None):
        """Helper method to make API requests"""
        # For custom API, the full URL might be provided or just the base URL
        if endpoint.startswith("http"):
            url = endpoint
        else:
            # Handle proxy URLs that need specific formatting
            if self.api_url.endswith('/openai'):
                # For proxy URLs ending with /openai, handle special case
                if endpoint == 'v1/chat/completions':
                    url = f"{self.api_url}/chat/completions"
                else:
                    url = f"{self.api_url}/{endpoint.replace('v1/', '')}"
            # Handle API URLs that already include the endpoint
            elif endpoint.lstrip('/') in self.api_url:
                url = self.api_url
            else:
                url = f"{self.api_url}/{endpoint.lstrip('/')}"
        
        print(f"Making request to: {url}")
            
        _headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        if headers:
            _headers.update(headers)
        
        try:    
            response = requests.post(url, json=payload, headers=_headers, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Status code: {e.response.status_code}")
                print(f"Response text: {e.response.text}")
            raise
    
    def dialogue(self, msg):
        chat_print("user", msg)
        
        # Add user message to history
        self.conversation_history.append({"role": "user", "content": msg})
        
        # Prepare the payload for OpenAI-compatible API
        payload = {
            "model": self.model_name,
            "messages": self.conversation_history,
            "max_tokens": 1024
        }
        
        # LOG THE FULL REQUEST
        print("\033[36m" + "=" * 60 + "\033[0m")
        print("\033[36m🔍 FULL API REQUEST DEBUG\033[0m")
        print("\033[36m" + "=" * 60 + "\033[0m")
        print(f"\033[36mURL: {self.api_url}/v1/chat/completions\033[0m")
        print(f"\033[36mModel: {self.model_name}\033[0m")
        print(f"\033[36mTotal messages: {len(self.conversation_history)}\033[0m")
        print("\033[36m" + "-" * 60 + "\033[0m")
        
        # Log each message with index and details
        for i, message in enumerate(self.conversation_history):
            print(f"\033[36mMessage {i}:\033[0m")
            print(f"  Role: {message['role']}")
            content = message['content']
            if isinstance(content, str):
                print(f"  Content (string): {content[:100]}{'...' if len(content) > 100 else ''}")
            elif isinstance(content, list):
                print(f"  Content (list): {len(content)} items")
                for j, item in enumerate(content):
                    print(f"    Item {j}: {type(item)} - {str(item)[:50]}{'...' if len(str(item)) > 50 else ''}")
            else:
                print(f"  Content (other): {type(content)} - {str(content)[:100]}{'...' if len(str(content)) > 100 else ''}")
            print()
        
        print("\033[36m" + "-" * 60 + "\033[0m")
        print("\033[36mFull payload JSON:\033[0m")
        import json
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        print("\033[36m" + "=" * 60 + "\033[0m")
        
        try:
            response = self._make_request("v1/chat/completions", payload)
            # Debug the response
            print(f"API response keys: {response.keys()}")
            
            assistant_msg = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            # Add assistant response to history
            self.conversation_history.append({"role": "assistant", "content": assistant_msg})
            
            chat_print("Custom", assistant_msg)
            
            # Try to convert to dict if possible
            try:
                result = eval(assistant_msg)
                return result
            except:
                return assistant_msg
                
        except Exception as e:
            print(f"Custom API error: {e}")
            return str(e)
    
    def dialogue_with_img(self, msg, img_path):
        chat_print("user", msg)
        
        # Encode image to base64
        import base64
        with open(img_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')
        
        # Detect if this is a Google AI/Gemini endpoint and format accordingly
        is_gemini = ('google' in self.api_url.lower() or 
                    'gemini' in self.model_name.lower() or
                    'models/' in self.model_name)
        
        if is_gemini:
            # Format for Google Gemini API
            user_message = {
                "role": "user",
                "content": [
                    {"type": "text", "text": msg},
                    {
                        "type": "inline_data",
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": base64_image  # No data:image/jpeg;base64, prefix for Gemini
                        }
                    }
                ]
            }
            print(f"\033[35m🤖 Using GEMINI image format\033[0m")
        else:
            # Format for OpenAI-compatible APIs
            user_message = {
                "role": "user",
                "content": [
                    {"type": "text", "text": msg},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
            }
            print(f"\033[35m🤖 Using OPENAI image format\033[0m")
        
        # Add to conversation history
        self.conversation_history.append(user_message)
        
        # Prepare the payload
        payload = {
            "model": self.model_name,
            "messages": self.conversation_history,
            "max_tokens": 1024
        }
        
        # LOG THE FULL REQUEST WITH IMAGE
        print("\033[35m" + "=" * 60 + "\033[0m")
        print(f"\033[35m🖼️ FULL API REQUEST DEBUG (WITH IMAGE) - {'GEMINI' if is_gemini else 'OPENAI'} FORMAT\033[0m")
        print("\033[35m" + "=" * 60 + "\033[0m")
        print(f"\033[35mURL: {self.api_url}/v1/chat/completions\033[0m")
        print(f"\033[35mModel: {self.model_name}\033[0m")
        print(f"\033[35mTotal messages: {len(self.conversation_history)}\033[0m")
        print(f"\033[35mImage file: {img_path}\033[0m")
        print(f"\033[35mImage size: {len(base64_image)} chars (base64)\033[0m")
        print(f"\033[35mAPI Format: {'Gemini/Google AI' if is_gemini else 'OpenAI-compatible'}\033[0m")
        print("\033[35m" + "-" * 60 + "\033[0m")
        
        # Log each message with index and details
        for i, message in enumerate(self.conversation_history):
            print(f"\033[35mMessage {i}:\033[0m")
            print(f"  Role: {message['role']}")
            content = message['content']
            if isinstance(content, str):
                print(f"  Content (string): {content[:100]}{'...' if len(content) > 100 else ''}")
            elif isinstance(content, list):
                print(f"  Content (list): {len(content)} items")
                for j, item in enumerate(content):
                    if item.get('type') in ['image_url', 'inline_data']:
                        print(f"    Item {j}: {item.get('type')} - [BASE64 IMAGE DATA TRUNCATED]")
                    else:
                        print(f"    Item {j}: {type(item)} - {str(item)[:50]}{'...' if len(str(item)) > 50 else ''}")
            else:
                print(f"  Content (other): {type(content)} - {str(content)[:100]}{'...' if len(str(content)) > 100 else ''}")
            print()
        
        print("\033[35m" + "-" * 60 + "\033[0m")
        print("\033[35mPayload structure (image data truncated):\033[0m")
        
        # Create a copy of payload with truncated image data for logging
        import json
        import copy
        log_payload = copy.deepcopy(payload)
        for message in log_payload['messages']:
            if isinstance(message['content'], list):
                for item in message['content']:
                    if item.get('type') == 'image_url':
                        item['image_url']['url'] = item['image_url']['url'][:100] + "...[TRUNCATED]"
                    elif item.get('type') == 'inline_data':
                        item['inline_data']['data'] = item['inline_data']['data'][:100] + "...[TRUNCATED]"
        
        print(json.dumps(log_payload, indent=2, ensure_ascii=False))
        print("\033[35m" + "=" * 60 + "\033[0m")
        
        try:
            response = self._make_request("v1/chat/completions", payload)
            assistant_msg = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            # Add assistant response to history
            self.conversation_history.append({"role": "assistant", "content": assistant_msg})
            
            chat_print("Custom", assistant_msg)
            
            # Try to convert to dict if possible
            try:
                result = eval(assistant_msg)
                return result
            except:
                return assistant_msg
                
        except Exception as e:
            print(f"Custom API error: {e}")
            return str(e)
    
    # These might or might not be supported depending on the custom API
    def stt(self, audio, language='en'):
        print("STT might not be supported by this custom API")
        return False
        
    def text_to_speech(self, text, output_file, voice='alloy', response_format="mp3", speed=1):
        print("TTS might not be supported by this custom API")
        return False


# APIHelper Factory
# =================================================================
class APIFactory:
    """Factory class to create appropriate API handler"""
    
    @staticmethod
    def create_api_handler(provider_type, api_key, **kwargs):
        """Create an instance of the appropriate API handler based on provider_type"""
        if provider_type.lower() == "openai":
            assistant_id = kwargs.get("assistant_id")
            assistant_name = kwargs.get("assistant_name", "Assistant")
            api_url = kwargs.get("api_url")
            timeout = kwargs.get("timeout", 30)
            return OpenAIHandler(api_key, assistant_id, assistant_name, api_url, timeout)
            
        elif provider_type.lower() == "anthropic":
            model_name = kwargs.get("model_name", "claude-3-opus-20240229")
            api_url = kwargs.get("api_url")
            timeout = kwargs.get("timeout", 30)
            return AnthropicHandler(api_key, model_name, api_url, timeout)
            
        elif provider_type.lower() == "openrouter":
            model_name = kwargs.get("model_name", "anthropic/claude-3-opus")
            api_url = kwargs.get("api_url")
            timeout = kwargs.get("timeout", 30)
            return OpenRouterHandler(api_key, model_name, api_url, timeout)
            
        elif provider_type.lower() == "custom":
            model_name = kwargs.get("model_name", "gpt-4")
            api_url = kwargs.get("api_url")
            timeout = kwargs.get("timeout", 30)
            return CustomAPIHandler(api_key, model_name, api_url, timeout)
            
        else:
            raise ValueError(f"Unsupported provider type: {provider_type}")


# Backward Compatibility
# =================================================================
class OpenAiHelper:
    """Backward compatibility wrapper for OpenAIHandler"""
    
    def __init__(self, api_key, assistant_id, assistant_name, timeout=30):
        self.handler = OpenAIHandler(api_key, assistant_id, assistant_name, timeout=timeout)
        
    def stt(self, *args, **kwargs):
        return self.handler.stt(*args, **kwargs)
        
    def speech_recognition_stt(self, *args, **kwargs):
        return self.handler.speech_recognition_stt(*args, **kwargs)
        
    def dialogue(self, *args, **kwargs):
        return self.handler.dialogue(*args, **kwargs)
        
    def dialogue_with_img(self, *args, **kwargs):
        return self.handler.dialogue_with_img(*args, **kwargs)
        
    def text_to_speech(self, *args, **kwargs):
        return self.handler.text_to_speech(*args, **kwargs)

