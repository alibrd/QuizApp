from __future__ import annotations

import csv
import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _get_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _get_time() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


# All available fields that can be logged
AVAILABLE_FIELDS = {
    # Common fields
    "timestamp", "date", "time", "session_id", "event_type",
    
    # AI exchange fields
    "provider", "model", "topic", "prompt", "raw_response",
    
    # Question/Answer fields
    "question_type", "question", "options", "correct_answer",
    "user_answer", "is_correct", "feedback",
    
    # Session result fields
    "score", "total_questions", "percent",
    
    # Session start fields
    "title", "role", "topics", "ai_config", "font_config",

    # Multi-agent pipeline fields
    "agent_role",          # e.g., "generator", "examiner", "finalizer"
    "step_order",          # int, sequential position in the pipeline
    "validation_status",   # bool, did the step produce valid JSON/schema?
    "processing_error",    # str, error message on failure (e.g., "No Response")
    "draft_content",       # intermediate JSON or raw text at this step
}

# Default fields if none specified
DEFAULT_FIELDS = {
    "timestamp", "session_id", "event_type", "topic", "question", 
    "user_answer", "is_correct", "score", "total_questions", "percent"
}


class NullLogger:
    """A no-op logger used when logging is disabled."""
    def log_event(self, *args, **kwargs) -> None:
        pass

    def log_ai_exchange(self, **kwargs) -> None:
        pass

    def log_question_answer(self, **kwargs) -> None:
        pass

    def log_session_result(self, **kwargs) -> None:
        pass

    def log_multi_agent_step(self, **kwargs) -> None:
        pass


@dataclass
class BaseLogger:
    """Base class with field filtering logic."""
    log_dir: str = "logs"
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    fields: List[str] = field(default_factory=lambda: list(DEFAULT_FIELDS))
    
    def __post_init__(self) -> None:
        os.makedirs(self.log_dir, exist_ok=True)
        # Convert to set for faster lookup, validate fields
        if self.fields == ["*"] or self.fields == "*":
            self._enabled_fields = AVAILABLE_FIELDS.copy()
        else:
            self._enabled_fields = set(self.fields) & AVAILABLE_FIELDS
    
    def _should_log(self, field_name: str) -> bool:
        """Check if a field should be included in logs."""
        return field_name in self._enabled_fields
    
    def _filter_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Filter data dict to only include enabled fields."""
        return {k: v for k, v in data.items() if self._should_log(k)}
    
    def _add_common_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Add common fields like timestamp, date, time, session_id."""
        common = {}
        if self._should_log("timestamp"):
            common["timestamp"] = _utc_now_iso()
        if self._should_log("date"):
            common["date"] = _get_date()
        if self._should_log("time"):
            common["time"] = _get_time()
        if self._should_log("session_id"):
            common["session_id"] = self.session_id
        return {**common, **data}


@dataclass
class AssessmentLogger(BaseLogger):
    """Writes one JSON object per line (JSONL) with field filtering."""
    file_path: str = field(init=False)

    def __post_init__(self) -> None:
        super().__post_init__()
        self.file_path = os.path.join(self.log_dir, f"session_{self.session_id}.jsonl")

    def log_event(self, event_type: str, payload: Dict[str, Any], *, ts: Optional[str] = None) -> None:
        data = {"event_type": event_type} if self._should_log("event_type") else {}
        data = self._add_common_fields(data)
        
        # Filter payload fields
        filtered_payload = self._filter_data(payload)
        data.update(filtered_payload)
        
        # Override timestamp if provided
        if ts and self._should_log("timestamp"):
            data["timestamp"] = ts
        
        with open(self.file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")

    def log_ai_exchange(
        self,
        *,
        provider: str,
        model: str,
        topic: str,
        prompt: str,
        raw_response: str,
        question: Optional[str] = None,
        options: Optional[Dict[str, str]] = None,
        correct_answer: Optional[str] = None,
    ) -> None:
        payload = {
            "provider": provider,
            "model": model,
            "topic": topic,
            "prompt": prompt,
            "raw_response": raw_response,
        }
        if question is not None:
            payload["question"] = question
        if options is not None:
            payload["options"] = options
        if correct_answer is not None:
            payload["correct_answer"] = correct_answer
        self.log_event("ai_exchange", payload)

    def log_question_answer(
        self,
        *,
        topic: str,
        question_type: str,
        question: str,
        user_answer: Any,
        is_correct: bool,
        feedback: str,
        options: Optional[Dict[str, str]] = None,
        correct_answer: Optional[str] = None,
    ) -> None:
        payload = {
            "topic": topic,
            "question_type": question_type,
            "question": question,
            "user_answer": user_answer,
            "is_correct": is_correct,
            "feedback": feedback,
        }
        if options is not None:
            payload["options"] = options
        if correct_answer is not None:
            payload["correct_answer"] = correct_answer
        self.log_event("question_answer", payload)

    def log_session_result(self, *, score: int, total_questions: int, percent: float) -> None:
        self.log_event("session_result", {
            "score": score,
            "total_questions": total_questions,
            "percent": percent,
        })

    def log_multi_agent_step(
        self,
        *,
        step_order: int,
        agent_role: str,
        topic: str,
        prompt: str,
        raw_response: str,
        validation_status: bool,
        processing_error: Optional[str] = None,
        draft_content: Optional[Any] = None,
    ) -> None:
        """
        Log a single step in the multi-agent pipeline.

        Args:
            step_order: Sequential index of this step within the pipeline run.
            agent_role: The agent role name (e.g., "generator", "examiner").
            topic: The question topic being processed.
            prompt: The full prompt sent to the AI for this step.
            raw_response: The raw text returned by the AI (captured BEFORE json.loads).
            validation_status: True if the response was valid JSON/schema, False otherwise.
            processing_error: Error description if the step failed (e.g., "No Response",
                              "JSONDecodeError: ..."). None on success.
            draft_content: The parsed JSON dict (on success) or the raw text (on failure)
                           representing the intermediate state at this step.
        """
        payload = {
            "step_order": step_order,
            "agent_role": agent_role,
            "topic": topic,
            "prompt": prompt,
            "raw_response": raw_response,
            "validation_status": validation_status,
        }
        if processing_error is not None:
            payload["processing_error"] = processing_error
        if draft_content is not None:
            payload["draft_content"] = draft_content
        self.log_event("multi_agent_step", payload)


@dataclass
class CsvLogger(BaseLogger):
    """Writes logs to CSV files with field filtering."""
    _file_path: str = field(init=False)
    _headers_written: bool = field(init=False, default=False)

    def __post_init__(self) -> None:
        super().__post_init__()
        self._file_path = os.path.join(self.log_dir, f"session_{self.session_id}.csv")
        self._headers_written = False

    def _get_ordered_fields(self) -> List[str]:
        """Get enabled fields in a consistent order."""
        # Define preferred order
        preferred_order = [
            "timestamp", "date", "time", "session_id", "event_type",
            "provider", "model", "topic", "question_type", "question", "options",
            "correct_answer", "user_answer", "is_correct", "feedback",
            "prompt", "raw_response", "score", "total_questions", "percent",
            "title", "role", "topics", "ai_config", "font_config",
            # Multi-agent fields at the end so single-shot rows just have empty cells
            "agent_role", "step_order", "validation_status",
            "processing_error", "draft_content",
        ]
        return [f for f in preferred_order if f in self._enabled_fields]

    def _write_row(self, data: Dict[str, Any]) -> None:
        """Write a row to CSV, creating headers if needed."""
        ordered_fields = self._get_ordered_fields()
        
        with open(self._file_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            
            # Write headers on first row
            if not self._headers_written:
                writer.writerow(ordered_fields)
                self._headers_written = True
            
            # Write data row
            row = []
            for field_name in ordered_fields:
                value = data.get(field_name, "")
                # Convert complex types to JSON strings
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False)
                row.append(value)
            writer.writerow(row)

    def log_event(self, event_type: str, payload: Dict[str, Any], *, ts: Optional[str] = None) -> None:
        data = {"event_type": event_type} if self._should_log("event_type") else {}
        data = self._add_common_fields(data)
        
        filtered_payload = self._filter_data(payload)
        data.update(filtered_payload)
        
        if ts and self._should_log("timestamp"):
            data["timestamp"] = ts
        
        self._write_row(data)

    def log_ai_exchange(
        self,
        *,
        provider: str,
        model: str,
        topic: str,
        prompt: str,
        raw_response: str,
        question: Optional[str] = None,
        options: Optional[Dict[str, str]] = None,
        correct_answer: Optional[str] = None,
    ) -> None:
        payload = {
            "provider": provider,
            "model": model,
            "topic": topic,
            "prompt": prompt,
            "raw_response": raw_response,
        }
        if question is not None:
            payload["question"] = question
        if options is not None:
            payload["options"] = options
        if correct_answer is not None:
            payload["correct_answer"] = correct_answer
        self.log_event("ai_exchange", payload)

    def log_question_answer(
        self,
        *,
        topic: str,
        question_type: str,
        question: str,
        user_answer: Any,
        is_correct: bool,
        feedback: str,
        options: Optional[Dict[str, str]] = None,
        correct_answer: Optional[str] = None,
    ) -> None:
        payload = {
            "topic": topic,
            "question_type": question_type,
            "question": question,
            "user_answer": user_answer,
            "is_correct": is_correct,
            "feedback": feedback,
        }
        if options is not None:
            payload["options"] = options
        if correct_answer is not None:
            payload["correct_answer"] = correct_answer
        self.log_event("question_answer", payload)

    def log_session_result(self, *, score: int, total_questions: int, percent: float) -> None:
        self.log_event("session_result", {
            "score": score,
            "total_questions": total_questions,
            "percent": percent,
        })

    def log_multi_agent_step(
        self,
        *,
        step_order: int,
        agent_role: str,
        topic: str,
        prompt: str,
        raw_response: str,
        validation_status: bool,
        processing_error: Optional[str] = None,
        draft_content: Optional[Any] = None,
    ) -> None:
        """
        Log a single step in the multi-agent pipeline to CSV.

        Fields that are not relevant to single-shot questions (e.g., step_order)
        will simply be empty cells for those rows, preserving backward compatibility.
        """
        payload = {
            "step_order": step_order,
            "agent_role": agent_role,
            "topic": topic,
            "prompt": prompt,
            "raw_response": raw_response,
            "validation_status": validation_status,
        }
        if processing_error is not None:
            payload["processing_error"] = processing_error
        if draft_content is not None:
            payload["draft_content"] = draft_content
        self.log_event("multi_agent_step", payload)


LoggerType = Union[AssessmentLogger, CsvLogger, NullLogger]


def create_logger(logger_type: Optional[str] = None, **kwargs) -> LoggerType:
    """
    Factory function to create the appropriate logger.
    
    Args:
        logger_type: "jsonl", "csv", or None/empty for no logging.
        **kwargs: Additional arguments (log_dir, fields).
    
    Returns:
        Logger instance.
    """
    if not logger_type:
        return NullLogger()
    
    logger_type = logger_type.lower()
    
    if logger_type == "jsonl":
        return AssessmentLogger(**kwargs)
    elif logger_type == "csv":
        return CsvLogger(**kwargs)
    else:
        return NullLogger()