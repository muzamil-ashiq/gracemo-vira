"""
GraceEMO Interaction — Unit Tests
No API key needed: tests run against the heuristics fallback only.
"""
import unittest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.models import InspectorState, AskQuestionRequest, AskQuestionResponse
from core.llm_engine import LLMEngine
from core.dialogue_engine import DialogueEngine
from core.interaction_loop import InteractionLoop


# ──────────────────────────────────────────────────────────────────────
# Model tests
# ──────────────────────────────────────────────────────────────────────

class TestInspectorState(unittest.TestCase):
    def test_defaults(self):
        s = InspectorState()
        self.assertEqual(s.battery, 98.5)
        self.assertEqual(s.current_task, "IDLE")

    def test_to_dict(self):
        s = InspectorState()
        d = s.to_dict()
        assert "pose" in d
        assert "battery" in d
        assert d["status"] == "READY"


# ──────────────────────────────────────────────────────────────────────
# Dialogue engine tests
# ──────────────────────────────────────────────────────────────────────

class TestDialogueEngine(unittest.TestCase):
    def setUp(self):
        self.de = DialogueEngine()

    def test_stop_intent(self):
        cmd = self.de.parse("stop now!")
        assert cmd.intent == "STOP"

    def test_halt_intent(self):
        cmd = self.de.parse("halt immediately")
        assert cmd.intent == "STOP"

    def test_navigate_intent(self):
        cmd = self.de.parse("go to the lab")
        assert cmd.intent == "NAVIGATE"

    def test_take_me_intent(self):
        cmd = self.de.parse("take me to reception")
        assert cmd.intent == "NAVIGATE"

    def test_greet_intent(self):
        cmd = self.de.parse("hello there")
        assert cmd.intent == "GREET"

    def test_hand_up_intent(self):
        cmd = self.de.parse("hands up")
        assert cmd.intent == "HAND_UP"

    def test_hand_down_intent(self):
        cmd = self.de.parse("hands down please")
        assert cmd.intent == "HAND_DOWN"

    def test_query_intent(self):
        cmd = self.de.parse("what is your name?")
        assert cmd.intent == "QUERY"

    def test_who_intent(self):
        cmd = self.de.parse("who are you")
        assert cmd.intent == "QUERY"

    def test_general_command(self):
        cmd = self.de.parse("dance robot")
        assert cmd.intent == "COMMAND"


# ──────────────────────────────────────────────────────────────────────
# LLM Engine heuristics tests (no API key required)
# ──────────────────────────────────────────────────────────────────────

class TestLLMEngineHeuristics(unittest.TestCase):
    """
    These tests use the _heuristics() method directly to validate
    fallback behavior. No API key / network required.
    """

    def setUp(self):
        # Force heuristics by using an engine with no backend set
        self.engine = LLMEngine.__new__(LLMEngine)
        self.engine._backend = None
        self.engine._gemini_client = None
        self.engine._gemini_legacy = None
        self.engine._groq_client = None
        self.engine._ollama_base = None

    def _h(self, q: str) -> AskQuestionResponse:
        return self.engine._heuristics(q)

    def test_stop(self):
        r = self._h("stop now")
        assert r.intent == "STOP"
        assert "stop" in r.suggested_actions

    def test_navigate(self):
        r = self._h("go to lab")
        assert r.intent == "NAVIGATE"
        assert any("navigate_to" in a for a in r.suggested_actions)

    def test_navigate_place_extraction(self):
        r = self._h("take me to the library")
        assert "library" in r.suggested_actions[0]

    def test_greet(self):
        r = self._h("hello gracemo")
        assert r.intent == "HAND_HI"

    def test_hand_up(self):
        r = self._h("hands up")
        assert r.intent == "HAND_UP"

    def test_hand_down(self):
        r = self._h("hands down")
        assert r.intent == "HAND_DOWN"

    def test_identity(self):
        r = self._h("who are you")
        assert r.intent == "IDENTITY"
        assert "GraceEMO" in r.answer

    def test_status(self):
        r = self._h("battery status")
        assert r.intent == "STATUS_REPORT"

    def test_fallback(self):
        r = self._h("do a backflip")
        assert r.intent == "GENERAL_QUERY"
        assert r.confidence < 0.9


# ──────────────────────────────────────────────────────────────────────
# Interaction loop integration tests
# ──────────────────────────────────────────────────────────────────────

class TestInteractionLoop(unittest.TestCase):
    def setUp(self):
        # No TTS for tests
        self.loop = InteractionLoop(enable_tts=False)

    def test_stop_command(self):
        result = self.loop.handle_text("stop!")
        assert result.action in ("stop", "speak")

    def test_navigate_command(self):
        result = self.loop.handle_text("go to lab")
        assert result.action == "navigate_to"
        assert "Lab" in result.target or "lab" in result.target.lower()

    def test_greet_command(self):
        result = self.loop.handle_text("hello")
        assert result.action == "speak"

    def test_hand_up(self):
        result = self.loop.handle_text("hands up")
        assert result.action == "speak"  # after hand_up, speak is returned

    def test_unknown_place(self):
        result = self.loop.handle_text("go to the moon")
        # Should either navigate_to or speak (with error)
        assert result.action in ("navigate_to", "speak")

    def test_action_hook(self):
        called = []
        self.loop.set_action_hook("speak", lambda text="": called.append(text))
        self.loop.handle_text("hello")
        assert len(called) > 0

    def test_state_update(self):
        self.loop.handle_text("who are you")
        assert self.loop.state.last_voice == "who are you"
