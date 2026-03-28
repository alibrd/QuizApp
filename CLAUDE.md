# CLAUDE.md — AI Assessment Suite (QuizApp)

## Project Overview

A Python/Tkinter desktop quiz application that dynamically generates assessment questions using LLM providers. Users load a JSON config file specifying topics, AI provider, question types, and optional features (flashcards, multi-agent pipeline, question sources). The app generates questions on the fly, tracks scores, and optionally logs sessions and creates flashcard CSVs.

## Tech Stack

- **Language**: Python 3.8+
- **GUI**: Tkinter (standard library)
- **AI Providers**: Groq, Google Gemini, Ollama, Hugging Face Inference API
- **Libraries**: `google-genai`, `ollama`, `groq`, `huggingface_hub`
- **Optional PDF support**: PyMuPDF (`fitz`) or PyPDF2

## How to Run

```bash
python main.py
```

The app opens a landing screen. Click "Load Quiz Configuration" and select a JSON config file. No CLI arguments.

## File Architecture

| File | Purpose |
|------|---------|
| `main.py` | Entry point. `QuizApp` class — GUI, config loading, AI client init, quiz flow orchestration |
| `question_types.py` | Question type hierarchy (abstract `Question` base + 4 subclasses) and `MultiAgentQuestion` orchestrator |
| `flashcard.py` | `FlashCard` dataclass, `FlashCardService` (AI generation), `FlashCardLogger` (CSV persistence), `FlashCardDialog` (selection UI) |
| `logger.py` | `AssessmentLogger` (JSONL), `CsvLogger` (CSV), `NullLogger` (no-op), `BaseLogger` (field filtering), `create_logger()` factory |
| `question_source.py` | `QuestionSource` — loads paragraphs from PDF/TXT, displays random paragraph in a separate Tkinter window |
| `*.json` | Config files (examples: `python_config.json`, `linux_config.json`, `python_config_multiagent.json`) |
| `flashcards/` | Output directory for flashcard CSV files |
| `Notes.txt` | Developer feature planning notes |

## Core Architecture

### Question Type Hierarchy (question_types.py)

Abstract base class `Question` with four concrete subclasses, each implementing:
- `get_prompt_instruction()` — LLM prompt text
- `get_json_schema()` — expected JSON schema for AI output
- `render_ui(parent_frame, font_config)` — Tkinter widgets
- `get_user_answer()` — extract user's selection
- `check_answer(user_answer)` — returns `(is_correct: bool, feedback: str)`

**Subclasses:**
- `MultipleChoiceQuestion` — 4 radio buttons (a/b/c/d)
- `TrueFalseQuestion` — true/false radio buttons
- `MultiSelectQuestion` — checkboxes, multiple correct answers
- `ShortAnswerQuestion` — text entry, exact-match comparison

**Type name mappings** (used in config `question_types` array):
- `"mcq"` / `"multiple_choice"` → `MultipleChoiceQuestion`
- `"tf"` / `"true_false"` → `TrueFalseQuestion`
- `"multi_select"` / `"multi"` → `MultiSelectQuestion`
- `"short"` / `"short_answer"` → `ShortAnswerQuestion`

Two mapping dicts exist: `QUESTION_TYPE_MAP` (in main.py) and `BASE_TYPE_MAP` (in question_types.py). They map the same aliases but `BASE_TYPE_MAP` is used by the multi-agent system.

### Multi-Agent Pipeline (question_types.py — `MultiAgentQuestion`)

An orchestrator that chains multiple AI "agents" (roles) to generate higher-quality questions. Configured via the `"multi_agent"` section of the JSON config.

**Pipeline flow**: `generator → [pedagogy_reviewer] → [examiner] → [finalizer]` (plus optional agents)

**Key design decisions:**
- `generator` is the only required role (must be first)
- All other roles are optional and composable in any order
- Only `generator` and `finalizer` receive the config's `role` context; reviewers evaluate objectively
- Each agent can use a different AI model via `role_models` config; unspecified roles fall back to `ai.model`
- Pipeline retries up to `max_attempts` on failure
- `_execute_and_log()` is the central helper that calls AI, parses JSON, and logs each step

**Available agents**: `generator`, `pedagogy_reviewer`, `examiner`/`judge`, `finalizer`, `distractor_specialist`, `difficulty_calibrator`, `deduplicator`

### Quiz Flow (main.py — `QuizApp`)

1. **Landing screen** → user loads JSON config via file dialog
2. **Config parsing** → sets topics, AI provider, question types, logger, flashcard config, multi-agent config, question source
3. **AI initialization** (`_init_ai()`) → creates client for the configured provider
4. **Quiz UI** → question text area, dynamic options frame, submit/next/end/flashcard buttons
5. **Question generation** (`load_new_question()`) → either single-shot or multi-agent path:
   - **Single-shot**: picks random topic + question class, generates prompt, fetches AI response, parses JSON
   - **Multi-agent**: delegates to `MultiAgentQuestion.generate_question_json()`
6. **Answer checking** (`check_answer()`) → polymorphic: delegates to `current_question_obj.check_answer()`
7. **Session end** (`finish_assessment()`) → logs results, shows score, returns to landing

### AI Provider Abstraction (main.py — `fetch_ai_response()`)

Single method handling all providers. Supports `model_override` parameter (used by multi-agent per-role models) and `json_mode` flag.

| Provider | Client | JSON Mode |
|----------|--------|-----------|
| `groq` | `Groq` client | `response_format={"type": "json_object"}` |
| `gemini`/`flash`/`lite` | `genai.GenerativeModel` | `response_mime_type="application/json"` |
| `ollama` | `ollama` module | `format="json"` |
| `huggingface`/`hf` | `InferenceClient` | `response_format={"type": "json_object"}` |

### Logging System (logger.py)

Factory pattern via `create_logger(type, **kwargs)`:
- `"jsonl"` → `AssessmentLogger` (one JSON object per line)
- `"csv"` → `CsvLogger` (columnar CSV with ordered headers)
- `None` → `NullLogger` (no-op, used when logging is disabled)

**Field filtering**: Configs specify which fields to log via `logger.fields` array. `"*"` enables all fields. Fields are validated against `AVAILABLE_FIELDS` set.

**Event types logged**: `session_start`, `ai_exchange`, `question_answer`, `session_result`, `multi_agent_step`, `session_end`

### Flashcard System (flashcard.py)

- `FlashCardService` — takes an `ai_fetcher` callable, generates flashcards from a question/answer pair via LLM
- `FlashCardLogger` — appends flashcards to a session CSV file (supports both auto-generated filenames and explicit `file_name` from config)
- `FlashCardDialog` — modal Tkinter dialog with checkboxes for selecting which flashcards to save
- Flashcard generation uses a separate model if `flashcard.model` is specified in config

### Question Source (question_source.py)

Optional feature: loads paragraphs from a PDF or TXT file. When active, displays a random paragraph in a separate window each time a new question is generated. Configured via `"question_source": "path/to/file"` in JSON config.

## JSON Config Schema

```jsonc
{
  "title": "Quiz Title",                    // Window title (optional)
  "role": "Act as a ...",                    // System prompt/persona (optional)
  "topics": ["topic1", "topic2"],            // REQUIRED — list of topics
  "font": {"family": "Verdana", "size": 12}, // Font config (optional)
  "ai": {
    "provider": "groq",                      // groq | gemini | flash | lite | ollama | huggingface | hf
    "model": "openai/gpt-oss-120b"           // Model name for the provider
  },
  "question_types": ["mcq", "tf", "multi_select", "short"], // Optional, defaults to all
  "logger": {
    "type": "jsonl",                         // jsonl | csv | omit for no logging
    "log_dir": "logs",
    "fields": ["timestamp", "question", "is_correct"]  // or "*" for all
  },
  "flashcard": {
    "count": 10,                             // Cards per generation
    "model": "llama-3.1-8b-instant",         // Optional override model
    "log_dir": "flashcards",
    "file_name": "existing.csv"              // Optional, null = auto-generate
  },
  "question_source": "C:/path/to/file.pdf",  // Optional PDF/TXT source
  "multi_agent": {
    "base_type": "mcq",                      // Optional fixed type, omit for random
    "roles": ["generator", "examiner", "finalizer"],
    "role_models": {                         // Per-agent model overrides
      "generator": "openai/gpt-oss-120b",
      "examiner": "llama-3.1-8b-instant"
    },
    "max_attempts": 3,
    "target_difficulty": 3                   // 1-5, used by difficulty_calibrator
  }
}
```

Topics prefixed with `%` appear in the config examples but have no special handling in code (likely a user convention for disabling topics).

## Environment Variables

- `GROQ_API_KEY` — required for Groq provider
- `GEMINI_API_KEY` — required for Gemini/Flash/Lite provider
- `HF_TOKEN` — required for Hugging Face provider
- Ollama requires a running local Ollama instance (no key needed)

## Key Design Patterns

- **Strategy/Polymorphism**: Question types share an abstract interface; quiz flow is type-agnostic
- **Factory**: `create_logger()` for logger instantiation
- **Null Object**: `NullLogger` avoids conditionals throughout the codebase
- **Composition**: `MultiAgentQuestion` composes AI calls into a pipeline without subclassing `Question`
- **Dependency Injection**: `FlashCardService` and `MultiAgentQuestion` receive `ai_fetcher` callables rather than creating their own clients

## Conventions

- AI responses are expected as raw JSON (no markdown fences); code strips ` ```json ``` ` as a safety measure
- All question data flows as Python dicts parsed from AI JSON responses
- The `data` dict on each `Question` instance holds the raw parsed AI response
- Tkinter `StringVar`/`BooleanVar` are used for user input binding
- Error recovery on question generation: retries after 1 second via `root.after()`
- Flashcard CSVs are headerless, two columns: `"question","answer"`
- Session log files are named with UUID session IDs
