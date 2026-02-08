import tkinter as tk
from abc import ABC, abstractmethod

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