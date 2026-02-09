from __future__ import annotations

import csv
import json
import os
import tkinter as tk
from dataclasses import dataclass, field
from datetime import datetime
from tkinter import ttk
from typing import Callable, List, Optional
import uuid


# --- DEFAULTS ---
DEFAULT_FLASHCARD_COUNT = 10


@dataclass
class FlashCard:
    """Represents a single flash card."""
    question: str
    answer: str


class FlashCardService:
    """Service to generate flash cards via AI."""
    
    PROMPT_TEMPLATE = """
    Based on this quiz question and answer, generate exactly {count} flash card-style 
    question/answer pairs that help reinforce the concept.
    
    Original Question: {question}
    Correct Answer: {answer}
    
    Return ONLY valid JSON (no markdown):
    {{
        "flashcards": [
            {{"question": "...", "answer": "..."}},
            {{"question": "...", "answer": "..."}}
        ]
    }}
    """
    
    def __init__(self, ai_fetcher: Callable[[str], str], count: int = DEFAULT_FLASHCARD_COUNT):
        """
        Args:
            ai_fetcher: Function that takes a prompt and returns AI response.
            count: Number of flash cards to generate.
        """
        self._fetch_ai = ai_fetcher
        self._count = count
    
    def generate_flashcards(self, question: str, answer: str) -> List[FlashCard]:
        """Generate flash cards from a question/answer pair."""
        prompt = self.PROMPT_TEMPLATE.format(
            count=self._count,
            question=question, 
            answer=answer
        )
        
        raw_response = self._fetch_ai(prompt)
        clean_text = raw_response.replace("```json", "").replace("```", "").strip()
        
        data = json.loads(clean_text)
        
        return [
            FlashCard(question=fc["question"], answer=fc["answer"])
            for fc in data.get("flashcards", [])
        ]


@dataclass
class FlashCardLogger:
    """Handles saving flash cards to a single CSV file per session (append mode)."""
    log_dir: str = "flashcards"
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    _file_path: str = field(init=False)
    _file_exists: bool = field(init=False, default=False)
    
    def __post_init__(self):
        os.makedirs(self.log_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._file_path = os.path.join(
            self.log_dir, f"flashcards_{timestamp}_{self.session_id}.csv"
        )
    
    @property
    def file_path(self) -> str:
        """Get the current session's file path."""
        return self._file_path
    
    def save_flashcards(self, flashcards: List[FlashCard], source_question: str = "") -> str:
        """
        Append flash cards to the session's CSV file.
        
        Args:
            flashcards: List of FlashCard objects to save.
            source_question: Original question (for reference, not saved).
        
        Returns:
            Path to the CSV file.
        """
        with open(self._file_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            for card in flashcards:
                writer.writerow([card.question, card.answer])
        
        self._file_exists = True
        return self._file_path
    
    @property
    def card_count(self) -> int:
        """Count total cards in the session file."""
        if not os.path.exists(self._file_path):
            return 0
        with open(self._file_path, "r", encoding="utf-8") as f:
            return sum(1 for _ in csv.reader(f))


class FlashCardDialog:
    """Modal dialog for selecting and saving flash cards."""
    
    def __init__(self, parent: tk.Tk, flashcards: List[FlashCard], 
                 logger: FlashCardLogger, source_question: str = "",
                 on_complete: Callable[[str, int], None] = None):
        """
        Args:
            parent: Parent Tkinter window.
            flashcards: List of FlashCard objects to display.
            logger: FlashCardLogger instance for saving.
            source_question: Original question for reference.
            on_complete: Callback with (file_path, saved_count) when cards are saved.
        """
        self.flashcards = flashcards
        self.logger = logger
        self.source_question = source_question
        self.on_complete = on_complete
        self.checkbox_vars: List[tk.BooleanVar] = []
        
        # Create modal window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Select Flash Cards")
        self.dialog.geometry("650x550")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self._build_ui()
    
    def _build_ui(self):
        # Header with session info
        header_frame = ttk.Frame(self.dialog)
        header_frame.pack(fill="x", pady=(10, 5), padx=15)
        
        ttk.Label(header_frame, text="Select flash cards to save:", 
                  font=("Arial", 12, "bold")).pack(side="left")
        
        # Show existing card count
        existing_count = self.logger.card_count
        if existing_count > 0:
            ttk.Label(header_frame, text=f"({existing_count} cards already in session)", 
                      foreground="gray").pack(side="right")
        
        # Select all checkbox
        self.select_all_var = tk.BooleanVar(value=True)
        select_all_cb = ttk.Checkbutton(
            self.dialog, text="Select All", variable=self.select_all_var,
            command=self._toggle_all
        )
        select_all_cb.pack(anchor="w", padx=15)
        
        # Scrollable frame for cards
        container = ttk.Frame(self.dialog)
        container.pack(fill="both", expand=True, padx=10, pady=5)
        
        canvas = tk.Canvas(container)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Enable mouse wheel scrolling
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))
        
        # Add checkboxes for each flashcard
        for i, card in enumerate(self.flashcards):
            var = tk.BooleanVar(value=True)
            self.checkbox_vars.append(var)
            
            frame = ttk.LabelFrame(self.scrollable_frame, text=f"Card {i+1}")
            frame.pack(fill="x", padx=5, pady=5)
            
            inner_frame = ttk.Frame(frame)
            inner_frame.pack(fill="x", padx=5, pady=5)
            
            cb = ttk.Checkbutton(inner_frame, variable=var)
            cb.pack(side="left", anchor="n")
            
            text_frame = ttk.Frame(inner_frame)
            text_frame.pack(side="left", fill="x", expand=True)
            
            q_label = ttk.Label(text_frame, text=f"Q: {card.question}", 
                               wraplength=550, justify="left")
            q_label.pack(anchor="w")
            
            a_label = ttk.Label(text_frame, text=f"A: {card.answer}", 
                               wraplength=550, justify="left", foreground="gray")
            a_label.pack(anchor="w")
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Buttons
        btn_frame = ttk.Frame(self.dialog)
        btn_frame.pack(fill="x", pady=10)
        
        ttk.Button(btn_frame, text="Cancel", 
                   command=self.dialog.destroy).pack(side="right", padx=10)
        ttk.Button(btn_frame, text="Add to Flash Cards", 
                   command=self._on_create).pack(side="right", padx=5)
    
    def _toggle_all(self):
        """Toggle all checkboxes based on Select All state."""
        state = self.select_all_var.get()
        for var in self.checkbox_vars:
            var.set(state)
    
    def _on_create(self):
        """Save selected flash cards and close dialog."""
        selected = [
            card for card, var in zip(self.flashcards, self.checkbox_vars) 
            if var.get()
        ]
        
        if not selected:
            from tkinter import messagebox
            messagebox.showwarning("No Selection", "Please select at least one flash card.")
            return
        
        file_path = self.logger.save_flashcards(selected, self.source_question)
        
        if self.on_complete:
            self.on_complete(file_path, len(selected))
        
        self.dialog.destroy()