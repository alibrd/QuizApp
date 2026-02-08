import tkinter as tk
from tkinter import messagebox, filedialog
import google.generativeai as genai
import ollama
from groq import Groq
import random
import os
import json
from logger import create_logger, NullLogger

# IMPORT THE NEW MODULE
from question_types import MultipleChoiceQuestion, TrueFalseQuestion, MultiSelectQuestion, ShortAnswerQuestion

# --- DEFAULTS ---
DEFAULT_FONT_FAMILY = "Arial"
DEFAULT_FONT_SIZE = 12
DEFAULT_CODE_FONT = "Courier New"
DEFAULT_AI_PROVIDER = "groq"
DEFAULT_AI_MODEL = "llama3-70b-8192" # Groq default

# Map question type names to classes
QUESTION_TYPE_MAP = {
    "mcq": MultipleChoiceQuestion,
    "multiple_choice": MultipleChoiceQuestion,
    "tf": TrueFalseQuestion,
    "true_false": TrueFalseQuestion,
    "multi_select": MultiSelectQuestion,
    "multi": MultiSelectQuestion,
    "short": ShortAnswerQuestion,
    "short_answer": ShortAnswerQuestion,
}

# All available question classes
ALL_QUESTION_CLASSES = [
    MultipleChoiceQuestion, 
    TrueFalseQuestion, 
    MultiSelectQuestion, 
    ShortAnswerQuestion
]

class QuizApp:
    def __init__(self, root):
        self.root = root
        self.root.geometry("900x750")
        self.root.title("AI Assessment Suite")

        # Configuration Containers
        self.config = {
            "title": "General Assessment",
            "role": "Act as a helpful tutor.",
            "topics": [],
            "font": {"family": DEFAULT_FONT_FAMILY, "size": DEFAULT_FONT_SIZE},
            "ai": {"provider": DEFAULT_AI_PROVIDER, "model": DEFAULT_AI_MODEL}
        }
        
        # State variables
        self.current_question_obj = None # Holds the instance of Question class
        self.total_questions = 0
        self.score = 0
        self.ai_client = None
        
        # Initialize with NullLogger (no logging until config is loaded)
        self.logger = NullLogger()
        
        # Build Main UI Container
        self.main_container = tk.Frame(self.root)
        self.main_container.pack(fill="both", expand=True)
        
        # Available Question Types (will be set from config or default to all)
        self.question_classes = ALL_QUESTION_CLASSES.copy()
        
        self.show_landing_screen()

    def _parse_question_types(self, question_types_config: list) -> list:
        """
        Parse question types from config and return list of question classes.
        
        Args:
            question_types_config: List of question type strings from JSON config.
        
        Returns:
            List of question class types.
        """
        if not question_types_config:
            return ALL_QUESTION_CLASSES.copy()
        
        selected_classes = []
        for q_type in question_types_config:
            q_type_lower = q_type.lower().strip()
            if q_type_lower in QUESTION_TYPE_MAP:
                question_class = QUESTION_TYPE_MAP[q_type_lower]
                if question_class not in selected_classes:
                    selected_classes.append(question_class)
            else:
                print(f"Warning: Unknown question type '{q_type}' ignored.")
        
        # If no valid types found, default to all
        if not selected_classes:
            print("Warning: No valid question types specified. Using all types.")
            return ALL_QUESTION_CLASSES.copy()
        
        return selected_classes

    def get_font(self, style="normal"):
        """Helper to get dynamic font"""
        family = self.config['font'].get('family', DEFAULT_FONT_FAMILY)
        base_size = self.config['font'].get('size', DEFAULT_FONT_SIZE)
        
        if style == "header":
            return (family, int(base_size * 1.8), "bold")
        elif style == "code":
            return (DEFAULT_CODE_FONT, int(base_size * 1.1), "normal")
        elif style == "bold":
            return (family, base_size, "bold")
        else:
            return (family, base_size, "normal")

    def clear_window(self):
        for widget in self.main_container.winfo_children():
            widget.destroy()

    # --- SCREEN 1: LANDING ---
    def show_landing_screen(self):
        self.clear_window()
        tk.Label(self.main_container, text="AI Assessment Loader", font=("Arial", 24, "bold")).pack(pady=60)
        
        tk.Button(self.main_container, text="📂 Load Quiz Configuration", 
                  font=("Arial", 16), bg="#4CAF50", fg="white", width=25, height=2,
                  command=self.load_configuration_file).pack(pady=30)

    def load_configuration_file(self):
        file_path = filedialog.askopenfilename(title="Select Quiz Config", filetypes=[("JSON Files", "*.json")])
        if not file_path: return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if "topics" not in data or not data["topics"]:
                raise ValueError("JSON must contain a list of 'topics'.")

            self.config.update({
                "title": data.get("title", self.config["title"]),
                "role": data.get("role", self.config["role"]),
                "topics": data.get("topics", [])
            })
            if "ai" in data: self.config["ai"] = data["ai"]
            
            # Add this line to update font family and size from JSON
            if "font" in data: self.config["font"].update(data["font"])

            # Parse question types from config
            question_types_config = data.get("question_types", [])
            self.question_classes = self._parse_question_types(question_types_config)

            if self._init_ai():
                # Create logger based on config (defaults to NullLogger if not specified)
                logger_config = data.get("logger", {})
                logger_type = logger_config.get("type")  # e.g., "jsonl" or None
                logger_options = {k: v for k, v in logger_config.items() if k != "type"}
                
                self.logger = create_logger(logger_type, **logger_options)
                
                self.logger.log_event("session_start", {
                    "title": self.config.get("title"),
                    "role": self.config.get("role"),
                    "topics": self.config.get("topics", []),
                    "ai": self.config.get("ai", {}),
                    "font": self.config.get("font", {}),
                    "question_types": [cls.__name__ for cls in self.question_classes],
                })
                self.start_quiz_ui()
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load: {str(e)}")

    # --- AI INITIALIZATION ---
    def _init_ai(self):
        provider = self.config['ai'].get('provider', DEFAULT_AI_PROVIDER).lower()
        try:
            if provider in ["flash", "lite", "gemini"]:
                genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
                self.ai_client = genai.GenerativeModel(self.config['ai'].get('model', 'gemini-1.5-flash'))
            elif provider == "groq":
                self.ai_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
            elif provider == "ollama":
                self.ai_client = ollama
            else:
                raise ValueError(f"Unknown provider: {provider}")
            return True
        except Exception as e:
            messagebox.showerror("AI Init Error", str(e))
            return False

    # --- SCREEN 2: QUIZ INTERFACE ---
    def start_quiz_ui(self):
        self.clear_window()
        self.root.title(self.config['title'])
        self.total_questions = 0
        self.score = 0

        # UI Setup
        self.header_label = tk.Label(self.main_container, text=self.config['title'], font=self.get_font("header"))
        self.header_label.pack(pady=15)

        # Question Text Area (Static)
        self.question_text = tk.Text(self.main_container, height=6, width=70, wrap=tk.WORD, 
                                     font=self.get_font("code"), bg="#f0f0f0", bd=0, padx=10, pady=10)
        self.question_text.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
        self.question_text.config(state=tk.DISABLED)

        # Dynamic Options Area (Content changes based on question type)
        self.options_frame = tk.Frame(self.main_container)
        self.options_frame.pack(pady=5, padx=20, fill="x")

        # Feedback Area
        self.feedback_label = tk.Label(self.main_container, text="", font=self.get_font("bold"))
        self.feedback_label.pack(pady=10)

        # Controls
        self.btn_frame = tk.Frame(self.main_container)
        self.btn_frame.pack(pady=15)
        
        self.submit_btn = tk.Button(self.btn_frame, text="Submit Answer", command=self.check_answer, 
                                    bg="#4CAF50", fg="white", font=self.get_font("bold"), width=15)
        self.submit_btn.grid(row=0, column=0, padx=10)

        self.next_btn = tk.Button(self.btn_frame, text="Next Question", command=self.load_new_question, 
                                  state=tk.DISABLED, font=self.get_font("bold"), width=15)
        self.next_btn.grid(row=0, column=1, padx=10)

        self.finish_btn = tk.Button(self.btn_frame, text="End Quiz", command=self.finish_assessment, 
                                    bg="#f44336", fg="white", font=self.get_font("bold"), width=15)
        self.finish_btn.grid(row=0, column=2, padx=10)

        self.status_label = tk.Label(self.main_container, text="Initializing...", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)

        self.load_new_question()

    # --- LOGIC ---
    def generate_prompt_text(self, topic, question_class):
        """Dynamic prompt generation based on the Question Class selected."""
        role = self.config.get("role", "Act as a helpful technical interviewer.")
        
        return f"""
        {role}
        
        {question_class.get_prompt_instruction()}
        Topic: "{topic}"

        GUIDELINES:
        - Return ONLY valid JSON.
        - No Markdown blocks (```json).
        - Use this EXACT JSON schema:
        {question_class.get_json_schema()}
        """

    def fetch_ai_response(self, prompt):
        """Handles the API call to different providers."""
        provider = self.config['ai']['provider'].lower()
        model = self.config['ai'].get('model', 'default')

        try:
            if provider in ["flash", "lite", "gemini"]:
                return self.ai_client.generate_content(prompt).text
            elif provider == "ollama":
                res = self.ai_client.chat(model=model, messages=[{'role': 'user', 'content': prompt}])
                return res['message']['content']
            elif provider == "groq":
                res = self.ai_client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model=model)
                return res.choices[0].message.content
        except Exception as e:
            print(f"AI Error: {e}")
            return ""

    def load_new_question(self):
        self.status_label.config(text="Generating new question...")
        self.root.update()

        try:
            # 1. Select Topic and Question Type
            topic = random.choice(self.config['topics'])
            
            # Randomly pick a question class from configured types
            SelectedClass = random.choice(self.question_classes)
            
            # 2. Generate Prompt specific to that class
            prompt = self.generate_prompt_text(topic, SelectedClass(topic, {})) # Temp instance for prompt
            
            # 3. Fetch & Parse
            raw_text = self.fetch_ai_response(prompt)
            clean_text = raw_text.replace("```json", "").replace("```", "").strip()
            
            try:
                data = json.loads(clean_text)
            except:
                raise ValueError("AI returned invalid JSON")

            # Log AI exchange WITH parsed question data
            provider = self.config["ai"]["provider"]
            model = self.config["ai"].get("model", "default")
            self.logger.log_ai_exchange(
                provider=provider,
                model=model,
                topic=topic,
                prompt=prompt,
                raw_response=raw_text,
                question=data.get("question", ""),
                options=data.get("options"),
                correct_answer=str(data.get("correct", "")),
            )

            # 4. Instantiate the Actual Question Object
            self.current_question_obj = SelectedClass(topic, data)

            # 5. Render UI
            self.question_text.config(state=tk.NORMAL)
            self.question_text.delete(1.0, tk.END)
            self.question_text.insert(tk.END, f"Type: {data.get('type', 'Standard').upper()} | Topic: {topic}\n\n{data['question']}")
            self.question_text.config(state=tk.DISABLED)

            # Clear old options and render new ones
            for widget in self.options_frame.winfo_children():
                widget.destroy()
            
            # POLYMORPHISM IN ACTION: 
            # We don't know what type of widgets are being drawn, we just ask the object to do it.
            self.current_question_obj.render_ui(self.options_frame, self.get_font("code"))

            # Reset Buttons/Labels
            self.feedback_label.config(text="")
            self.submit_btn.config(state=tk.NORMAL)
            self.next_btn.config(state=tk.DISABLED)
            self.status_label.config(text=f"Question {self.total_questions + 1} ready.")

        except Exception as e:
            print(e)
            self.status_label.config(text="Error generating. Retrying...")
            self.root.after(1000, self.load_new_question)

    def check_answer(self):
        if not self.current_question_obj: return

        user_ans = self.current_question_obj.get_user_answer()

        if not user_ans and user_ans != False:
             messagebox.showwarning("Warning", "Please provide an answer.")
             return

        is_correct, feedback = self.current_question_obj.check_answer(user_ans)

        # Log Q/A with full details
        q_data = getattr(self.current_question_obj, "data", {})
        
        self.logger.log_question_answer(
            topic=getattr(self.current_question_obj, "topic", "unknown"),
            question_type=str(q_data.get("type", "unknown")),
            question=q_data.get("question", "unknown"),
            options=q_data.get("options"),  # May be None for TF/Short
            correct_answer=str(q_data.get("correct", "")),
            user_answer=user_ans,
            is_correct=is_correct,
            feedback=feedback,
        )

        self.total_questions += 1
        if is_correct:
            self.score += 1
            self.feedback_label.config(text=feedback, fg="green")
        else:
            self.feedback_label.config(text=feedback, fg="red")

        self.submit_btn.config(state=tk.DISABLED)
        self.next_btn.config(state=tk.NORMAL)

    def finish_assessment(self):
        pct = (self.score / self.total_questions * 100) if self.total_questions > 0 else 0

        self.logger.log_session_result(
            score=self.score,
            total_questions=self.total_questions,
            percent=round(pct, 1),
        )
        self.logger.log_event("session_end", {})

        messagebox.showinfo("Result", f"Score: {self.score}/{self.total_questions}\n({pct:.1f}%)")
        self.show_landing_screen()

if __name__ == "__main__":
    root = tk.Tk()
    app = QuizApp(root)
    root.mainloop()