# 🎯 AI Assessment Suite

A configurable quiz application that generates dynamic questions using AI providers (Groq, Gemini, Ollama). Built with Python and Tkinter.

## ✨ Features

- **AI-Powered Question Generation** - Dynamically generates questions using LLMs
- **Multiple Question Types**:
  - Multiple Choice (MCQ)
  - True/False
  - Multi-Select (multiple correct answers)
  - Short Answer (code snippets/keywords)
- **Configurable via JSON** - Customize topics, AI provider, fonts, and logging
- **Session Logging** - Track questions and answers in JSONL or CSV format
- **Cross-Provider Support** - Works with Groq, Google Gemini, and Ollama

## 📋 Requirements

- Python 3.8+
- Dependencies:

## 🔧 Installation

1. Clone the repository
2. Install dependencies:

## 🚀 Usage

1. Run the application:
2. Click **"Load Quiz Configuration"** and select a JSON config file
3. Answer the generated questions and track your score

## ⚙️ Configuration

Create a JSON configuration file to customize your quiz:

### Configuration Options

| Key | Description | Required |
|-----|-------------|----------|
| `title` | Quiz window title | No |
| `role` | AI persona/instructions | No |
| `topics` | List of topics for questions | **Yes** |
| `font` | Font family and size | No |
| `ai.provider` | `groq`, `gemini`, `flash`, `lite`, or `ollama` | No |
| `ai.model` | Model name for the provider | No |
| `question_types` | Array: `mcq`, `tf`, `multi_select`, `short` | No |
| `logger.type` | `jsonl`, `csv`, or omit for no logging | No |
| `logger.log_dir` | Directory for log files | No |
| `logger.fields` | Fields to include in logs | No |

## 📁 Project Structure

## 📝 License

MIT License