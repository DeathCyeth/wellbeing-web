# AI Companion Setup

## Overview
The AI Companion uses OpenAI's GPT-3.5-turbo to provide personalized wellbeing advice based on:
- User preferences (likes/dislikes)
- Doctor notes
- User's name and context

## Setup Instructions

### Step 1: Get OpenAI API Key

1. Go to https://platform.openai.com/
2. Sign up or log in
3. Navigate to API Keys section
4. Create a new API key
5. Copy the key (you'll need it in Step 2)

### Step 2: Set Environment Variable

**Windows PowerShell:**
```powershell
$env:OPENAI_API_KEY="your-api-key-here"
```

**Windows Command Prompt:**
```cmd
set OPENAI_API_KEY=your-api-key-here
```

**To make it permanent (Windows):**
1. Open System Properties → Environment Variables
2. Add new User variable:
   - Name: `OPENAI_API_KEY`
   - Value: `your-api-key-here`

**Linux/Mac:**
```bash
export OPENAI_API_KEY="your-api-key-here"
```

### Step 3: Install OpenAI Package

```bash
pip install openai
```

Or:
```bash
pip install -r requirements.txt
```

### Step 4: Restart the Server

After setting the environment variable, restart your Flask server:

1. Stop the current server (Ctrl+C)
2. Start it again: `python server.py`

## Testing

1. Log in as a patient
2. Go to the "AI Companion" section
3. Ask a question like: "I would like a recipe for a healthy breakfast"
4. The AI should respond with personalized advice

## Troubleshooting

### "OpenAI not configured" error
- Make sure you've installed: `pip install openai`
- Verify the package is installed: `python -c "import openai; print(openai.__version__)"`

### "OpenAI API key not configured" error
- Check that OPENAI_API_KEY environment variable is set
- Restart the server after setting the variable
- Verify with: `echo $env:OPENAI_API_KEY` (PowerShell) or `echo $OPENAI_API_KEY` (Linux/Mac)

### "AI service error"
- Check your OpenAI API key is valid
- Verify you have credits in your OpenAI account
- Check the server console for detailed error messages

## Cost Considerations

- OpenAI charges per API call (very affordable for personal use)
- GPT-3.5-turbo is cost-effective
- Monitor usage at https://platform.openai.com/usage

## Security Note

⚠️ **Never commit your API key to version control!**
- Always use environment variables
- Don't share your API key
- Keep it secure

