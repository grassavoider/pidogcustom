# PiDog Multi-API Support

This implementation extends the original PiDog OpenAI integration to support multiple API providers:

- OpenAI (default)
- Anthropic/Claude
- OpenRouter
- Custom OpenAI-compatible endpoints

## Configuration Options

### Command Line Arguments

You can configure the API provider directly from the command line:

```bash
# Use OpenAI (default)
python gpt_dog.py

# Use OpenRouter
python gpt_dog.py --provider openrouter --api-key your-openrouter-key --model anthropic/claude-3-opus

# Use Anthropic/Claude
python gpt_dog.py --provider anthropic --api-key your-anthropic-key --model claude-3-opus-20240229

# Use a custom OpenAI-compatible endpoint
python gpt_dog.py --provider custom --api-key your-api-key --api-url https://your-custom-endpoint.com --model gpt-4

# Use a configuration file
python gpt_dog.py --config your_config.json
```

### Configuration File

For more convenient setup, create a JSON configuration file based on the provided template:

1. Copy `api_config_template.json` to a new file (e.g., `my_config.json`)
2. Edit the file to uncomment and configure your preferred provider
3. Run PiDog with `--config my_config.json`

## Provider-Specific Considerations

### OpenAI

- Requires an assistant ID for OpenAI Assistants API
- Supports STT and TTS natively
- Example configuration:
  ```json
  {
    "provider": "openai",
    "api_key": "your-openai-api-key-here",
    "assistant_id": "your-assistant-id-here",
    "assistant_name": "PiDog"
  }
  ```

### Anthropic/Claude

- Uses Claude's chat completions API
- Supports image analysis with Claude 3
- STT handled by Google Speech Recognition
- TTS handled by OpenAI's TTS service (requires OpenAI API key)
- Example configuration:
  ```json
  {
    "provider": "anthropic",
    "api_key": "your-anthropic-api-key-here",
    "model_name": "claude-3-opus-20240229"
  }
  ```

### OpenRouter

- Acts as a proxy to multiple API providers
- Use model names like `anthropic/claude-3-opus` or `openai/gpt-4o`
- STT handled by Google Speech Recognition
- TTS handled by OpenAI's TTS service (requires OpenAI API key)
- Example configuration:
  ```json
  {
    "provider": "openrouter",
    "api_key": "your-openrouter-api-key-here",
    "model_name": "anthropic/claude-3-opus"
  }
  ```

### Custom API

- For self-hosted models or other OpenAI-compatible endpoints
- Configure the full URL to your API endpoint
- STT handled by Google Speech Recognition
- TTS handled by OpenAI's TTS service (requires OpenAI API key)
- Example configuration:
  ```json
  {
    "provider": "custom",
    "api_key": "your-api-key-here",
    "model_name": "gpt-4",
    "api_url": "https://your-custom-api-endpoint.com"
  }
  ```

## API Response Format

For all providers, the response should be a string or a dictionary with the following format:

```json
{
  "answer": "The text response to be spoken",
  "actions": ["action1", "action2", "action3"]
}
```

The available actions include: "sit", "stand", "sleep", "stop", "look_left", "look_right", "look_up", "look_down", "look_straight", "feet_left_right", "walk_forward", "walk_backward", "turn_left", "turn_right", "waiting", "bark", "bark harder", "pant", "howling", etc.

## Limitations

- Non-OpenAI providers do not have built-in STT functionality; Google Speech Recognition is used as a fallback
- Non-OpenAI providers do not have built-in TTS functionality; OpenAI's TTS service is used as a fallback (requires an OpenAI API key)
- While using a non-OpenAI provider as the main API, you still need an OpenAI API key for TTS functionality 