import tkinter as tk
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Callable, Any
import json


# --- BASE CLASS ---
class Question(ABC):
    def __init__(self, topic, data):
        self.topic = topic
        self.data = data
        self.user_answer_vars = None 

    @abstractmethod
    def get_prompt_instruction(self):
        pass

    @staticmethod
    @abstractmethod
    def get_json_schema():
        pass

    @abstractmethod
    def render_ui(self, parent_frame, font_config):
        pass

    @abstractmethod
    def get_user_answer(self):
        pass

    @abstractmethod
    def check_answer(self, user_answer):
        pass


# --- SUBCLASSES ---

class MultipleChoiceQuestion(Question):
    def get_prompt_instruction(self):
        return f"Generate a multiple-choice question about {self.topic} with 4 options and 1 correct answer. Make the options detailed."

    @staticmethod
    def get_json_schema():
        return """
        {
            "type": "mcq",
            "question": "Question text...",
            "options": {"a": "...", "b": "...", "c": "...", "d": "..."},
            "correct": "a"
        }
        """

    def render_ui(self, parent_frame, font_config):
        self.user_answer_vars = tk.StringVar(value="unselected")
        self.option_widgets = [] # Keep track of widgets to update wrap length
        
        # 1. Create a dedicated container for this question
        # This ensures bindings are destroyed when the question is cleared
        self.container = tk.Frame(parent_frame)
        self.container.pack(fill="x", expand=True)

        options = self.data.get('options', {})
        for key, text in options.items():
            rb = tk.Radiobutton(
                self.container,
                text=f"{key.upper()}. {text}",
                variable=self.user_answer_vars,
                value=key,
                font=font_config,
                anchor="w", justify="left"
            )
            rb.pack(fill="x", pady=5)
            self.option_widgets.append(rb)

        # 2. Bind the resize event to update text wrapping dynamically
        self.container.bind("<Configure>", self._on_resize)

    def _on_resize(self, event):
        """Update wraplength when the window is resized."""
        # Subtracting 30px provides a buffer so text doesn't touch the edge
        wrap_width = event.width - 30 
        
        if wrap_width < 100: return # Prevent errors if minimized

        for widget in self.option_widgets:
            widget.config(wraplength=wrap_width)

    def get_user_answer(self):
        val = self.user_answer_vars.get()
        return val if val != "unselected" else None

    def check_answer(self, user_answer):
        correct = self.data['correct'].lower()
        if user_answer == correct:
            return True, "Correct!"
        return False, f"Incorrect. The correct answer was {correct.upper()}."


class TrueFalseQuestion(Question):
    def get_prompt_instruction(self):
        return f"Generate a True/False question about {self.topic}."

    @staticmethod
    def get_json_schema():
        return """
        {
            "type": "tf",
            "question": "Statement text...",
            "correct": "true" 
        }
        """

    def render_ui(self, parent_frame, font_config):
        self.user_answer_vars = tk.StringVar(value="unselected")
        
        # TF usually doesn't need wrapping, but we use a container for consistency
        self.container = tk.Frame(parent_frame)
        self.container.pack(fill="x", expand=True)
        
        for val in ["true", "false"]:
            rb = tk.Radiobutton(
                self.container,
                text=val.title(),
                variable=self.user_answer_vars,
                value=val,
                font=font_config,
                anchor="w"
            )
            rb.pack(fill="x", pady=5)

    def get_user_answer(self):
        val = self.user_answer_vars.get()
        return val if val != "unselected" else None

    def check_answer(self, user_answer):
        correct = str(self.data['correct']).lower()
        if user_answer == correct:
            return True, "Correct!"
        return False, f"Incorrect. The answer is {correct.title()}."


class MultiSelectQuestion(Question):
    def get_prompt_instruction(self):
        return f"Generate a difficult question about {self.topic} where TWO or MORE options are correct."

    @staticmethod
    def get_json_schema():
        return """
        {
            "type": "multi_select",
            "question": "Question text...",
            "options": {"a": "...", "b": "...", "c": "...", "d": "..."},
            "correct": ["a", "c"] 
        }
        """

    def render_ui(self, parent_frame, font_config):
        self.user_answer_vars = {} 
        self.option_widgets = []
        
        self.container = tk.Frame(parent_frame)
        self.container.pack(fill="x", expand=True)
        
        lbl = tk.Label(self.container, text="(Select all that apply)", font=("Arial", 10, "italic"))
        lbl.pack(anchor="w")

        options = self.data.get('options', {})
        for key, text in options.items():
            var = tk.BooleanVar()
            self.user_answer_vars[key] = var
            cb = tk.Checkbutton(
                self.container,
                text=f"{key.upper()}. {text}",
                variable=var,
                font=font_config,
                anchor="w", justify="left"
            )
            cb.pack(fill="x", pady=5)
            self.option_widgets.append(cb)
            
        # Bind resize for multi-select too, as these can also be long
        self.container.bind("<Configure>", self._on_resize)

    def _on_resize(self, event):
        wrap_width = event.width - 30
        if wrap_width < 100: return
        for widget in self.option_widgets:
            widget.config(wraplength=wrap_width)

    def get_user_answer(self):
        return [k for k, v in self.user_answer_vars.items() if v.get()]

    def check_answer(self, user_answer):
        correct = sorted([x.lower() for x in self.data['correct']])
        user = sorted([x.lower() for x in user_answer])
        
        if user == correct:
            return True, "Correct!"
        return False, f"Incorrect. Required: {', '.join(correct).upper()}"


class ShortAnswerQuestion(Question):
    def get_prompt_instruction(self):
        return f"""Generate a question about {self.topic} that requires a specific one-line code snippet or keyword answer.

If the question involves variables, specify them below the question text using this format:
- "input variable: <name>" for any pre-existing variables the user should use
- "output variable: <name>" for the variable the user should assign the result to

Examples:
1. Question with output only:
   "Write the code to create a dictionary with {{"a":1, "b":2}}
   output variable: x"
   Answer: x = {{"a":1, "b":2}}

2. Question with input and output:
   "Write the code to create a string from an integer
   input variable: x
   output variable: y"
   Answer: y = str(x)

3. Question with no variables:
   "What keyword is used to define a function in Python?"
   Answer: def

Only include variable specifications when the question requires them. Omit them for keyword or concept questions."""

    @staticmethod
    def get_json_schema():
        return """
        {
            "type": "short",
            "question": "Write the code to create a string from an integer\\ninput variable: x\\noutput variable: y",
            "correct": "y = str(x)"
        }
        """

    def render_ui(self, parent_frame, font_config):
        self.user_answer_vars = tk.StringVar()
        
        # No complex wrapping needed for the Entry widget itself
        entry = tk.Entry(parent_frame, textvariable=self.user_answer_vars, font=("Courier New", 12))
        entry.pack(fill="x", pady=10)
        entry.focus_set()

    def get_user_answer(self):
        return self.user_answer_vars.get()

    def check_answer(self, user_answer):
        clean_user = user_answer.strip().lower()
        clean_correct = self.data['correct'].strip().lower()
        
        if clean_user == clean_correct:
            return True, "Correct!"
        return False, f"Incorrect. Expected: {self.data['correct']}"


# --- MULTI-AGENT QUESTION ORCHESTRATOR ---

# Base type name to class mapping (used by MultiAgentQuestion)
BASE_TYPE_MAP = {
    "mcq": MultipleChoiceQuestion,
    "multiple_choice": MultipleChoiceQuestion,
    "tf": TrueFalseQuestion,
    "true_false": TrueFalseQuestion,
    "multi_select": MultiSelectQuestion,
    "multi": MultiSelectQuestion,
    "short": ShortAnswerQuestion,
    "short_answer": ShortAnswerQuestion,
}


class MultiAgentQuestion:
    """
    Orchestrates multiple AI roles to generate higher-quality questions.
    
    This is a wrapper that produces a final JSON conforming to one of the
    existing base question schemas (MCQ, TF, Multi-Select, Short).
    
    The multi-agent pipeline executes roles sequentially, with each role
    refining or validating the question before the finalizer produces
    the output.
    
    ================================================================================
    MULTI-AGENT PIPELINE DOCUMENTATION
    ================================================================================
    
    1. HOW THE MULTI-AGENT PIPELINE WORKS
    --------------------------------------
    The pipeline executes a sequence of AI "agents" (roles), each with a specific
    responsibility. Data flows through the pipeline as follows:
    
        generator ? pedagogy_reviewer ? examiner ? finalizer
                          ?                 ?
                    (feedback JSON)   (feedback JSON)
                          ???????????????????
                                   ?
                              finalizer
                                   ?
                          (final question JSON)
    
    Each agent receives input, processes it, and outputs structured JSON:
    
    - GENERATOR: Creates the initial candidate question based on topic and schema.
      Output: Question JSON matching the base type schema (mcq, tf, etc.)
    
    - PEDAGOGY_REVIEWER (optional): Evaluates clarity, learning value, and wording.
      Output: Feedback JSON with accept/reject, issues list, and suggested edits.
    
    - EXAMINER/JUDGE (optional): Validates correctness, schema compliance, and detects ambiguity.
      Output: Feedback JSON with errors, required fixes, and quality score.
    
    - FINALIZER (optional but recommended): Applies all feedback and produces the final corrected question.
      Output: Final question JSON matching the required schema exactly.
    
    - DISTRACTOR_SPECIALIST (optional): Improves wrong answer options (MCQ/multi-select only)
      Output: Improved question JSON with better distractors.
    
    - DIFFICULTY_CALIBRATOR (optional): Adjusts question difficulty to target level (1-5)
      Output: Calibrated question JSON.
    
    - DEDUPLICATOR (optional): Checks for similar questions in the session
      Output: Duplicate check result JSON.
    
    The pipeline retries up to `max_attempts` times if validation fails.
    
    2. FLEXIBLE AGENT COMPOSITION (ARBITRARY NESTING)
    --------------------------------------------------
    All agents EXCEPT "generator" are OPTIONAL. You can compose any combination
    of agents in any order. The only requirement is:
    
        - "generator" MUST be first (creates the initial question)
        - All other agents are optional and can be arranged in any order
    
    The pipeline executes agents in the exact order specified in the "roles" array.
    If an agent is not included, it is simply skipped. Feedback from skipped agents
    will be passed as "None" to downstream agents.
    
    EXAMPLE CONFIGURATIONS:
    
    (a) Minimal - Generator only (fastest, lowest quality):
        "roles": ["generator"]
        
        Flow: generator ? output
        Use case: Quick prototyping, when speed matters more than quality
    
    (b) Two agents - Generator + Finalizer (fast with refinement):
        "roles": ["generator", "finalizer"]
        
        Flow: generator ? finalizer ? output
        Use case: Basic refinement without review overhead
    
    (c) Generator + Examiner (correctness focus):
        "roles": ["generator", "examiner", "finalizer"]
        
        Flow: generator ? examiner ? finalizer ? output
        Use case: When correctness validation is critical, skip pedagogy review
    
    (d) Generator + Pedagogy Reviewer (learning quality focus):
        "roles": ["generator", "pedagogy_reviewer", "finalizer"]
        
        Flow: generator ? pedagogy_reviewer ? finalizer ? output
        Use case: When learning quality matters more than strict validation
    
    (e) Full pipeline (highest quality, slowest):
        "roles": ["generator", "pedagogy_reviewer", "examiner", "finalizer"]
        
        Flow: generator ? pedagogy_reviewer ? examiner ? finalizer ? output
        Use case: Production-quality questions with full review
    
    (f) With difficulty calibration:
        "roles": ["generator", "examiner", "difficulty_calibrator", "finalizer"]
        
        Flow: generator ? examiner ? difficulty_calibrator ? finalizer ? output
        Use case: When you need questions at a specific difficulty level
    
    (g) MCQ with distractor specialist:
        "roles": ["generator", "distractor_specialist", "examiner", "finalizer"]
        
        Flow: generator ? distractor_specialist ? examiner ? finalizer ? output
        Use case: High-quality MCQ with improved wrong answer options
    
    (h) Maximum quality pipeline (all agents):
        "roles": ["generator", "pedagogy_reviewer", "distractor_specialist", 
                  "examiner", "difficulty_calibrator", "finalizer"]
        
        Flow: generator ? pedagogy_reviewer ? distractor_specialist ? 
              examiner ? difficulty_calibrator ? finalizer ? output
        Use case: Highest possible quality, suitable for final exam creation
    
    (i) Deduplication-aware pipeline:
        "roles": ["generator", "deduplicator", "examiner", "finalizer"]
        
        Flow: generator ? deduplicator ? examiner ? finalizer ? output
        Use case: Long quiz sessions where question repetition is a concern
    
    JSON CONFIG EXAMPLES:
    
    Minimal (generator only):
    {
        "multi_agent": {
            "roles": ["generator"],
            "max_attempts": 3
        }
    }
    
    Fast with refinement:
    {
        "multi_agent": {
            "roles": ["generator", "finalizer"],
            "role_models": {
                "generator": "llama-3.1-8b-instant",
                "finalizer": "openai/gpt-oss-120b"
            }
        }
    }
    
    Correctness-focused (no pedagogy):
    {
        "multi_agent": {
            "roles": ["generator", "examiner", "finalizer"],
            "role_models": {
                "generator": "openai/gpt-oss-120b",
                "examiner": "llama-3.1-8b-instant",
                "finalizer": "openai/gpt-oss-120b"
            }
        }
    }
    
    Full quality pipeline:
    {
        "multi_agent": {
            "roles": ["generator", "pedagogy_reviewer", "examiner", "finalizer"],
            "role_models": {
                "generator": "openai/gpt-oss-120b",
                "pedagogy_reviewer": "llama-3.1-8b-instant",
                "examiner": "llama-3.1-8b-instant",
                "finalizer": "openai/gpt-oss-120b"
            },
            "max_attempts": 3
        }
    }
    
    MCQ with difficulty calibration:
    {
        "multi_agent": {
            "base_type": "mcq",
            "roles": ["generator", "distractor_specialist", "difficulty_calibrator", "finalizer"],
            "target_difficulty": 4,
            "role_models": {
                "generator": "openai/gpt-oss-120b",
                "finalizer": "openai/gpt-oss-120b"
            }
        }
    }
    
    3. HOW TO CONFIGURE IN THE JSON CONFIG FILE
    --------------------------------------------
    Add a "multi_agent" section to your config JSON:
    
    {
        "role": "Act as a Python professor...",    // Original role context
        "ai": {
            "provider": "groq",
            "model": "openai/gpt-oss-120b"         // Default fallback model
        },
        "question_types": ["mcq", "tf", "short"],  // Random selection if no base_type
        "multi_agent": {
            "base_type": "mcq",                    // Optional: fixed type, or omit for random
            "roles": ["generator", "pedagogy_reviewer", "examiner", "finalizer"],
            "role_models": {                       // Optional: per-agent model overrides
                "generator": "openai/gpt-oss-120b",
                "examiner": "llama-3.1-8b-instant",
                "finalizer": "openai/gpt-oss-120b"
            },
            "max_attempts": 3,                     // Retry budget on failure
            "target_difficulty": 3                 // 1=easy, 5=expert (for difficulty_calibrator)
        }
    }
    
    To disable multi-agent mode, simply omit the "multi_agent" section entirely.
    The app will then use single-shot question generation (existing behavior).
    
    4. ROLE CONTEXT AWARENESS (GENERATOR & FINALIZER ONLY)
    -------------------------------------------------------
    The "role" field from the config JSON (e.g., "Act as a Python professor...")
    is passed to the pipeline as `role_context`. However, NOT all agents receive it:
    
        ???????????????????????????????????????????????????????????????????????????
        ? Agent                   ? Knows Role?     ? Reason                      ?
        ???????????????????????????????????????????????????????????????????????????
        ? generator               ? ? YES          ? Creates questions in the    ?
        ?                         ?                 ? intended style/context      ?
        ???????????????????????????????????????????????????????????????????????????
        ? pedagogy_reviewer       ? ? NO           ? Should evaluate objectively ?
        ?                         ?                 ? without context bias        ?
        ???????????????????????????????????????????????????????????????????????????
        ? examiner                ? ? NO           ? Should validate correctness ?
        ?                         ?                 ? objectively                 ?
        ???????????????????????????????????????????????????????????????????????????
        ? distractor_specialist   ? ? NO           ? Focuses on distractor       ?
        ?                         ?                 ? quality, not style          ?
        ???????????????????????????????????????????????????????????????????????????
        ? difficulty_calibrator   ? ? NO           ? Adjusts difficulty          ?
        ?                         ?                 ? objectively                 ?
        ???????????????????????????????????????????????????????????????????????????
        ? deduplicator            ? ? NO           ? Compares questions          ?
        ?                         ?                 ? objectively                 ?
        ???????????????????????????????????????????????????????????????????????????
        ? finalizer               ? ? YES          ? Ensures final output        ?
        ?                         ?                 ? matches intended style/tone ?
        ???????????????????????????????????????????????????????????????????????????
    
    This design ensures:
    - Generator creates questions tailored to the specified context
    - Reviewers provide unbiased, objective feedback
    - Finalizer preserves the original intended style while applying fixes
    
    5. AI MODEL ASSIGNMENT FOR AGENTS
    ----------------------------------
    Each agent can use a different AI model. The model is determined as follows:
    
        1. Check if the agent is specified in "role_models" in the config
        2. If found ? use that model
        3. If NOT found ? fall back to "ai.model" (the default model)
    
    Example with this config:
    
        "ai": { "model": "openai/gpt-oss-120b" },      // Default fallback
        "multi_agent": {
            "roles": ["generator", "pedagogy_reviewer", "examiner", "finalizer"],
            "role_models": {                       // Optional: per-agent model overrides
                "generator": "openai/gpt-oss-120b",
                "examiner": "llama-3.1-8b-instant",
                "finalizer": "openai/gpt-oss-120b"
                // NOTE: pedagogy_reviewer is NOT specified here
            }
        }
    
    Resulting model assignments:
    
        ???????????????????????????????????????????????????????????????????????
        ? Agent               ? Model Source            ? Actual Model Used   ?
        ???????????????????????????????????????????????????????????????????????
        ? generator           ? role_models.generator   ? openai/gpt-oss-120b ?
        ? pedagogy_reviewer   ? FALLBACK to ai.model    ? openai/gpt-oss-120b ?
        ? examiner            ? role_models.examiner    ? llama-3.1-8b-instant?
        ? finalizer           ? role_models.finalizer   ? openai/gpt-oss-120b ?
        ???????????????????????????????????????????????????????????????????????
    
    The fallback logic is implemented in _call_ai() which passes model_override
    to the ai_fetcher. When model_override is None, main.py's fetch_ai_response()
    uses the default "ai.model" from the config.
    
    6. AVAILABLE AGENTS SUMMARY
    ---------------------------
        ???????????????????????????????????????????????????????????????????????????
        ? Agent                   ? Required ? Description                        ?
        ???????????????????????????????????????????????????????????????????????????
        ? generator               ? ? YES   ? Creates initial question           ?
        ? pedagogy_reviewer       ? ? NO    ? Evaluates learning quality         ?
        ? examiner / judge        ? ? NO    ? Validates correctness & schema     ?
        ? finalizer               ? ? NO    ? Applies feedback, produces output  ?
        ? distractor_specialist   ? ? NO    ? Improves MCQ wrong answers         ?
        ? difficulty_calibrator   ? ? NO    ? Adjusts difficulty (1-5)           ?
        ? deduplicator            ? ? NO    ? Checks for similar questions       ?
        ???????????????????????????????????????????????????????????????????????????
    
    ================================================================================
    """
    
    # --- ROLE PROMPT TEMPLATES ---
    
    GENERATOR_PROMPT = """
You are a QUESTION GENERATOR for an exam preparation system.

Your role: Create a high-quality {base_type} question about the topic.

Topic: {topic}

Context/Role: {role_context}

Requirements:
- Generate a question that tests understanding, not just recall
- Include plausible distractors (wrong answers should be believable)
- Ensure the question is clear and unambiguous
- The correct answer must be definitively correct

You MUST output ONLY valid JSON matching this EXACT schema:
{schema}

Output ONLY the JSON. No explanations, no markdown, no additional text.
"""

    PEDAGOGY_REVIEWER_PROMPT = """
You are a PEDAGOGY REVIEWER for exam questions.

Your role: Evaluate the learning quality and clarity of this question.

Question to review:
{candidate_json}

Evaluate for:
1. Clarity: Is the question easy to understand?
2. Learning value: Does it test meaningful understanding?
3. Wording quality: Is the language precise and professional?
4. Distractor quality: Are wrong answers plausible but clearly wrong?
5. Cognitive level: Does it require thinking, not just memorization?

You MUST output ONLY valid JSON in this EXACT format:
{{
    "accept": true or false,
    "issues": ["issue1", "issue2"],
    "suggested_edits": "Natural language suggestions for improvement",
    "clarity_score": 0.0 to 1.0,
    "learning_value_score": 0.0 to 1.0
}}

Output ONLY the JSON. No explanations, no markdown.
"""

    EXAMINER_PROMPT = """
You are an EXAMINER/JUDGE for exam questions.

Your role: Validate correctness, detect ambiguity, and ensure schema compliance.

Question to examine:
{candidate_json}

Required schema:
{schema}

Previous reviewer feedback (if any):
{reviewer_feedback}

Validate:
1. Correctness: Is the marked answer definitively correct?
2. Schema compliance: Does the JSON match the required format exactly?
3. Ambiguity: Could multiple answers be considered correct?
4. Exam quality: No trick questions, no giveaways, no vague wording
5. Answer count: Correct number of correct answers for the question type

You MUST output ONLY valid JSON in this EXACT format:
{{
    "accept": true or false,
    "errors": ["error1", "error2"],
    "required_fixes": ["fix1", "fix2"],
    "score": 0.0 to 1.0,
    "schema_valid": true or false
}}

Output ONLY the JSON. No explanations, no markdown.
"""

    FINALIZER_PROMPT = """
You are a FINALIZER for exam questions.

Context/Role: {role_context}

Your role: Apply all feedback and produce the FINAL corrected question.

Original question:
{candidate_json}

Pedagogy reviewer feedback:
{pedagogy_feedback}

Examiner feedback:
{examiner_feedback}

Required output schema:
{schema}

Instructions:
1. Apply all suggested fixes and improvements
2. Ensure the final question is clear, correct, and high-quality
3. Maintain the style and tone specified in the Context/Role above
4. Output MUST match the required schema EXACTLY
5. Do NOT add any extra keys or metadata

Output ONLY the final JSON. No explanations, no markdown, no additional text.
"""

    DISTRACTOR_SPECIALIST_PROMPT = """
You are a DISTRACTOR SPECIALIST for multiple-choice questions.

Your role: Improve the quality of wrong answer options (distractors).

Question to improve:
{candidate_json}

Requirements for good distractors:
1. Plausible: Should seem reasonable to someone who doesn't know the answer
2. Distinct: Each distractor should represent a different misconception
3. Not tricky: Should not be "gotcha" answers
4. Similar length/format to correct answer

You MUST output ONLY valid JSON matching this schema:
{schema}

Output ONLY the improved question JSON. No explanations.
"""

    DIFFICULTY_CALIBRATOR_PROMPT = """
You are a DIFFICULTY CALIBRATOR for exam questions.

Your role: Adjust question difficulty to the target level.

Question to calibrate:
{candidate_json}

Target difficulty: {target_difficulty} (1=easy, 5=expert)

Adjustments to make:
- For easier: Simplify language, more obvious correct answer
- For harder: Add nuance, require deeper understanding

You MUST output ONLY valid JSON matching this schema:
{schema}

Output ONLY the calibrated question JSON. No explanations.
"""

    DEDUPLICATOR_PROMPT = """
You are a DEDUPLICATOR for exam questions.

Your role: Check if this question is too similar to recently asked questions.

New question:
{candidate_json}

Recent questions in this session:
{recent_questions}

Evaluate:
1. Concept overlap: Does it test the exact same concept?
2. Wording similarity: Is the phrasing too similar?
3. Answer overlap: Are the correct answers identical?

You MUST output ONLY valid JSON in this EXACT FORMAT:
{{
    "is_duplicate": true or false,
    "similarity_score": 0.0 to 1.0,
    "similar_to_index": null or index number,
    "recommendation": "accept" or "regenerate"
}}

Output ONLY the JSON. No explanations.
"""

    def __init__(
        self,
        base_type: str,
        roles: List[str],
        topic: str,
        ai_fetcher: Callable[[str, Optional[str]], str],
        role_models: Optional[Dict[str, str]] = None,
        max_attempts: int = 3,
        role_context: str = "",
        target_difficulty: int = 3,
        logger: Optional[Any] = None,
    ):
        """
        Initialize the multi-agent question orchestrator.
        
        Args:
            base_type: Target question type ("mcq", "tf", "multi_select", "short")
            roles: Ordered list of roles to execute
            topic: The topic for the question
            ai_fetcher: Function(prompt, model_override) -> str
            role_models: Optional dict mapping role names to model overrides
            max_attempts: Maximum retry attempts on failure
            role_context: Additional context/role for the AI (passed to generator & finalizer only)
            target_difficulty: Difficulty level 1-5 (used by difficulty_calibrator)
            logger: Optional logger for debugging
        """
        if base_type.lower() not in BASE_TYPE_MAP:
            raise ValueError(f"Unknown base_type: {base_type}. Valid: {list(BASE_TYPE_MAP.keys())}")
        
        self.base_type = base_type.lower()
        self.base_class = BASE_TYPE_MAP[self.base_type]
        self.roles = roles
        self.topic = topic
        self.ai_fetcher = ai_fetcher
        self.role_models = role_models or {}
        self.max_attempts = max_attempts
        self.role_context = role_context
        self.target_difficulty = target_difficulty
        self.logger = logger
        
        # Pipeline state
        self._candidate_json: Optional[Dict] = None
        self._pedagogy_feedback: Optional[Dict] = None
        self._examiner_feedback: Optional[Dict] = None
        self._execution_log: List[Dict] = []
        self._step_counter: int = 0
    
    def _get_schema(self) -> str:
        """Get the JSON schema for the base question type."""
        return self.base_class.get_json_schema()
    
    def _call_ai(self, prompt: str, role: str) -> str:
        """
        Call AI with optional per-role model override.
        
        If the role is not specified in self.role_models, model_override will be None,
        and the ai_fetcher (main.py's fetch_ai_response) will fall back to the default
        model specified in config["ai"]["model"].
        """
        model_override = self.role_models.get(role)  # None if role not in role_models
        return self.ai_fetcher(prompt, model_override)
    
    def _parse_json(self, raw_text: str) -> Dict:
        """Parse JSON from AI response, stripping markdown if present."""
        clean = raw_text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean)
    
    def _log(self, role: str, status: str, data: Any = None):
        """Log role execution to local execution log for debugging."""
        entry = {"role": role, "status": status, "data": data}
        self._execution_log.append(entry)
    
    def _execute_and_log(self, role: str, prompt: str) -> Dict:
        """
        Central helper: call AI, capture raw response, parse JSON, and log
        the step to self.logger immediately.

        On success: logs validation_status=True with parsed dict as draft_content.
        On failure: logs validation_status=False with raw text as draft_content
                    and the error message as processing_error, then re-raises.

        Returns:
            Parsed JSON dict from the AI response.

        Raises:
            ValueError: If AI returns empty/no response.
            json.JSONDecodeError: If response is not valid JSON.
        """
        self._step_counter += 1
        step_order = self._step_counter

        raw = self._call_ai(prompt, role)

        # Guard against empty / None responses
        if not raw or not raw.strip():
            error_msg = "No Response"
            self._log(role, "error", error_msg)
            if self.logger:
                self.logger.log_multi_agent_step(
                    step_order=step_order,
                    agent_role=role,
                    topic=self.topic,
                    prompt=prompt,
                    raw_response="",
                    validation_status=False,
                    processing_error=error_msg,
                    draft_content=None,
                )
            raise ValueError(error_msg)

        try:
            result = self._parse_json(raw)
        except (json.JSONDecodeError, ValueError) as parse_err:
            error_msg = f"{type(parse_err).__name__}: {parse_err}"
            self._log(role, "error", error_msg)
            if self.logger:
                self.logger.log_multi_agent_step(
                    step_order=step_order,
                    agent_role=role,
                    topic=self.topic,
                    prompt=prompt,
                    raw_response=raw,
                    validation_status=False,
                    processing_error=error_msg,
                    draft_content=raw,  # Raw text preserved for debugging
                )
            raise

        # Success path
        self._log(role, "success", result)
        if self.logger:
            self.logger.log_multi_agent_step(
                step_order=step_order,
                agent_role=role,
                topic=self.topic,
                prompt=prompt,
                raw_response=raw,
                validation_status=True,
                processing_error=None,
                draft_content=result,
            )
        return result
    
    def _execute_generator(self) -> Dict:
        """
        Execute the generator role to create initial question.
        
        NOTE: Generator receives role_context to create questions in the intended style.
        """
        prompt = self.GENERATOR_PROMPT.format(
            base_type=self.base_type.upper(),
            topic=self.topic,
            role_context=self.role_context,
            schema=self._get_schema(),
        )
        return self._execute_and_log("generator", prompt)
    
    def _execute_pedagogy_reviewer(self, candidate: Dict) -> Dict:
        """
        Execute pedagogy reviewer to check learning quality.
        
        NOTE: Pedagogy reviewer does NOT receive role_context to ensure objective evaluation.
        """
        prompt = self.PEDAGOGY_REVIEWER_PROMPT.format(
            candidate_json=json.dumps(candidate, indent=2),
        )
        return self._execute_and_log("pedagogy_reviewer", prompt)
    
    def _execute_examiner(self, candidate: Dict, reviewer_feedback: Optional[Dict]) -> Dict:
        """
        Execute examiner to validate correctness and schema.
        
        NOTE: Examiner does NOT receive role_context to ensure objective validation.
        """
        feedback_str = json.dumps(reviewer_feedback, indent=2) if reviewer_feedback else "None"
        
        prompt = self.EXAMINER_PROMPT.format(
            candidate_json=json.dumps(candidate, indent=2),
            schema=self._get_schema(),
            reviewer_feedback=feedback_str,
        )
        return self._execute_and_log("examiner", prompt)
    
    def _execute_finalizer(
        self,
        candidate: Dict,
        pedagogy_feedback: Optional[Dict],
        examiner_feedback: Optional[Dict],
    ) -> Dict:
        """
        Execute finalizer to produce the corrected final question.
        
        NOTE: Finalizer receives role_context to ensure final output matches
        the intended style and tone from the original config role.
        """
        prompt = self.FINALIZER_PROMPT.format(
            candidate_json=json.dumps(candidate, indent=2),
            pedagogy_feedback=json.dumps(pedagogy_feedback, indent=2) if pedagogy_feedback else "None",
            examiner_feedback=json.dumps(examiner_feedback, indent=2) if examiner_feedback else "None",
            schema=self._get_schema(),
            role_context=self.role_context,
        )
        return self._execute_and_log("finalizer", prompt)
    
    def _execute_distractor_specialist(self, candidate: Dict) -> Dict:
        """Execute distractor specialist to improve wrong answers."""
        prompt = self.DISTRACTOR_SPECIALIST_PROMPT.format(
            candidate_json=json.dumps(candidate, indent=2),
            schema=self._get_schema(),
        )
        return self._execute_and_log("distractor_specialist", prompt)
    
    def _execute_difficulty_calibrator(self, candidate: Dict) -> Dict:
        """Execute difficulty calibrator to adjust question difficulty."""
        prompt = self.DIFFICULTY_CALIBRATOR_PROMPT.format(
            candidate_json=json.dumps(candidate, indent=2),
            target_difficulty=self.target_difficulty,
            schema=self._get_schema(),
        )
        return self._execute_and_log("difficulty_calibrator", prompt)
    
    def _execute_deduplicator(self, candidate: Dict, recent_questions: List[Dict]) -> Dict:
        """Check for duplicate/similar questions in session."""
        prompt = self.DEDUPLICATOR_PROMPT.format(
            candidate_json=json.dumps(candidate, indent=2),
            recent_questions=json.dumps(recent_questions, indent=2),
        )
        return self._execute_and_log("deduplicator", prompt)
    
    def _validate_schema(self, data: Dict) -> bool:
        """Basic schema validation for the base question type."""
        required_keys = {"question"}
        
        if self.base_type in ("mcq", "multiple_choice"):
            required_keys.update({"options", "correct", "type"})
            if not isinstance(data.get("options"), dict):
                return False
            if not isinstance(data.get("correct"), str):
                return False
        elif self.base_type in ("tf", "true_false"):
            required_keys.update({"correct", "type"})
            if str(data.get("correct", "")).lower() not in ("true", "false"):
                return False
        elif self.base_type in ("multi_select", "multi"):
            required_keys.update({"options", "correct", "type"})
            if not isinstance(data.get("correct"), list):
                return False
        elif self.base_type in ("short", "short_answer"):
            required_keys.update({"correct", "type"})
        
        return all(key in data for key in required_keys)
    
    def generate_question_json(self) -> Dict:
        """
        Execute the multi-agent pipeline and return the final question JSON.
        
        Returns:
            Dict conforming to the base question type schema.
        
        Raises:
            RuntimeError: If max_attempts exceeded without valid output.
        """
        last_error = None
        
        for attempt in range(self.max_attempts):
            try:
                self._execution_log = []
                self._candidate_json = None
                self._pedagogy_feedback = None
                self._examiner_feedback = None
                
                for role in self.roles:
                    if role == "generator":
                        self._candidate_json = self._execute_generator()
                    
                    elif role == "pedagogy_reviewer":
                        if self._candidate_json:
                            self._pedagogy_feedback = self._execute_pedagogy_reviewer(
                                self._candidate_json
                            )
                    
                    elif role in ("examiner", "judge"):
                        if self._candidate_json:
                            self._examiner_feedback = self._execute_examiner(
                                self._candidate_json,
                                self._pedagogy_feedback,
                            )
                    
                    elif role == "finalizer":
                        if self._candidate_json:
                            self._candidate_json = self._execute_finalizer(
                                self._candidate_json,
                                self._pedagogy_feedback,
                                self._examiner_feedback,
                            )
                    
                    elif role == "distractor_specialist":
                        if self._candidate_json and self.base_type in ("mcq", "multi_select"):
                            self._candidate_json = self._execute_distractor_specialist(
                                self._candidate_json
                            )
                    
                    elif role == "difficulty_calibrator":
                        if self._candidate_json:
                            self._candidate_json = self._execute_difficulty_calibrator(
                                self._candidate_json
                            )
                    
                    elif role == "deduplicator":
                        if self._candidate_json:
                            # Pass recent questions from the session history
                            recent_questions = [
                                q for q in self.execution_log 
                                if q.get("status") == "success" and q.get("data")
                            ]
                            
                            self._candidate_json = self._execute_deduplicator(
                                self._candidate_json,
                                recent_questions
                            )
                    
                    else:
                        self._log(role, "skipped", "Unknown role")
                
                # Validate final output
                if self._candidate_json and self._validate_schema(self._candidate_json):
                    self._log("pipeline", "success", {"attempt": attempt + 1})
                    return self._candidate_json
                else:
                    raise ValueError("Final output failed schema validation")
                    
            except Exception as e:
                last_error = e
                self._log("pipeline", "retry", {"attempt": attempt + 1, "error": str(e)})
                continue
        
        raise RuntimeError(
            f"Multi-agent pipeline failed after {self.max_attempts} attempts. "
            f"Last error: {last_error}"
        )
    
    @property
    def execution_log(self) -> List[Dict]:
        """Get the execution log for debugging."""
        return self._execution_log.copy()