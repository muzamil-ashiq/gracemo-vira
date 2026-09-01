#!/usr/bin/env python3
"""
GraceEMO cortex — intent + suggested_actions for the kernel.
Uses Gemini when GEMINI_API_KEY is set; otherwise campus heuristics.
"""

import json
import os
import re
import rclpy
from rclpy.node import Node

try:
    from gracemo_interfaces.srv import AskQuestion
    HAVE_INTERFACES = True
except ImportError:
    HAVE_INTERFACES = False

DEFAULT_PLACES = ('door', 'lab', 'reception', 'commons', 'kitchen', 'robotics', 'ai', 'library', 'mall', 'gate')


def extract_place_heuristic(text):
    t = text.lower()
    for p in DEFAULT_PLACES:
        if p in t:
            return p
    return 'door'


class LLMReasoningNode(Node):
    def __init__(self):
        super().__init__('llm_node')
        self.gemini = None
        self.gemini_sdk_type = None  # 'genai' or 'google.generativeai'

        api_key = os.environ.get('GEMINI_API_KEY', '') or os.environ.get('GOOGLE_API_KEY', '')
        if api_key:
            # 1. Try modern google.genai SDK
            try:
                from google import genai
                self.gemini = genai.Client(api_key=api_key)
                self.gemini_sdk_type = 'genai'
                self.get_logger().info('Gemini 2.0 Flash primary cortex online (google.genai SDK)')
            except Exception as e1:
                # 2. Fall back to google.generativeai
                try:
                    import google.generativeai as legacy_genai
                    legacy_genai.configure(api_key=api_key)
                    self.gemini = legacy_genai.GenerativeModel('gemini-2.0-flash')
                    self.gemini_sdk_type = 'google.generativeai'
                    self.get_logger().info('Gemini 2.0 Flash primary cortex online (google.generativeai legacy SDK)')
                except Exception as e2:
                    self.get_logger().warn(f'Gemini SDK initialization failed ({e1}; {e2}); using heuristics fallback')
        else:
            self.get_logger().info('No GEMINI_API_KEY set; using campus heuristics as safety fallback')

        if HAVE_INTERFACES:
            self.create_service(AskQuestion, '/gracemo/ask_question', self.handle_question)
        self.get_logger().info('LLM reasoning service active on /gracemo/ask_question')

    def _call_gemini(self, question: str, context: str) -> dict:
        """Call Gemini to reason over sensory context and user query."""
        system_instruction = (
            "You are GraceEMO, an autonomous wheeled campus assistant robot at Lovely Professional University (LPU).\n"
            "You are equipped with differential drive wheels, a pan/tilt neck camera, and dual 90-degree pitch arms.\n"
            "Analyze the user's query and current sensory/telemetry context.\n"
            "Return a strictly valid JSON object (no markdown, no backticks) with this exact schema:\n"
            "{\n"
            '  "answer": "1 concise, polite spoken sentence for TTS playback",\n'
            '  "intent": "NAVIGATE" | "STOP" | "GREET" | "HAND_HI" | "HAND_UP" | "HAND_DOWN" | "LOOK_AT" | "STATUS_REPORT" | "IDENTITY" | "GENERAL_QUERY",\n'
            '  "confidence": 0.95,\n'
            '  "suggested_actions": ["navigate_to:<place>"] | ["stop"] | ["hand_hi"] | ["hand_up"] | ["hand_down"] | ["speak"]\n'
            "}\n"
            "Available campus places: door, lab, reception, commons, kitchen, robotics, ai, library, mall, gate."
        )

        user_content = f"Sensory State Context: {context}\nUser Voice Query: \"{question}\""

        raw_text = ""
        if self.gemini_sdk_type == 'genai':
            resp = self.gemini.models.generate_content(
                model='gemini-2.0-flash',
                contents=f"{system_instruction}\n\n{user_content}"
            )
            raw_text = (resp.text or '').strip()
        elif self.gemini_sdk_type == 'google.generativeai':
            prompt = f"{system_instruction}\n\n{user_content}"
            result = self.gemini.generate_content(prompt)
            raw_text = (result.text or '').strip()

        # Parse JSON
        if raw_text:
            # Strip potential ```json wrapper
            clean_json = re.sub(r'^```(?:json)?\s*', '', raw_text)
            clean_json = re.sub(r'\s*```$', '', clean_json).strip()
            return json.loads(clean_json)

        raise ValueError("Empty response from Gemini")

    def handle_question(self, request, response):
        q = request.question.strip()
        self.get_logger().info(f'🧠 Cognitive reasoning over: "{q}"')

        # ---------------------------------------------------------------------
        # 1. PRIMARY PATH: Gemini 2.0 Flash Cortex
        # ---------------------------------------------------------------------
        if self.gemini is not None:
            try:
                parsed = self._call_gemini(q, request.context or "Normal campus state")
                response.answer = str(parsed.get('answer', 'I understand.'))
                response.intent = str(parsed.get('intent', 'GENERAL_QUERY')).upper()
                response.confidence = float(parsed.get('confidence', 0.92))
                actions = parsed.get('suggested_actions', ['speak'])
                if isinstance(actions, list):
                    response.suggested_actions = [str(a) for a in actions]
                else:
                    response.suggested_actions = ['speak']
                self.get_logger().info(f'✨ Gemini Cortex response: {response.answer} (intent={response.intent})')
                return response
            except Exception as e:
                self.get_logger().warn(f'Gemini primary cortex error ({e}); degrading gracefully to heuristic safety net')

        # ---------------------------------------------------------------------
        # 2. FALLBACK PATH: Deterministic Campus Safety Heuristics
        # ---------------------------------------------------------------------
        q_lower = q.lower()

        if any(w in q_lower for w in ('stop', 'halt', 'freeze', 'emergency')):
            response.answer = 'Stopping immediately.'
            response.intent = 'STOP'
            response.confidence = 0.99
            response.suggested_actions = ['stop']
            return response

        if any(w in q_lower for w in ('go to', 'navigate', 'take me', 'drive to')):
            place = extract_place_heuristic(q)
            response.answer = f'Navigating to {place}.'
            response.intent = 'NAVIGATE'
            response.confidence = 0.95
            response.suggested_actions = [f'navigate_to:{place}']
            return response

        if 'wave' in q_lower or 'hand hi' in q_lower or 'hello' in q_lower or 'hi' in q_lower:
            response.answer = 'Hello! Welcome to LPU campus.'
            response.intent = 'HAND_HI'
            response.confidence = 0.95
            response.suggested_actions = ['hand_hi', 'speak']
            return response

        if 'hands up' in q_lower or 'hand up' in q_lower:
            response.answer = 'Raising both hands.'
            response.intent = 'HAND_UP'
            response.confidence = 0.95
            response.suggested_actions = ['hand_up']
            return response

        if 'hands down' in q_lower or 'hand down' in q_lower:
            response.answer = 'Lowering hands to resting position.'
            response.intent = 'HAND_DOWN'
            response.confidence = 0.95
            response.suggested_actions = ['hand_down']
            return response

        if 'who are you' in q_lower or 'your name' in q_lower:
            response.answer = (
                'I am GraceEMO, an autonomous assistant robot at Lovely Professional University. '
                'I drive on 4 wheels and can speak, wave, and navigate campus.'
            )
            response.intent = 'IDENTITY'
            response.confidence = 0.99
            response.suggested_actions = ['speak']
            return response

        if 'battery' in q_lower or 'status' in q_lower:
            response.answer = 'All campus robotics systems are operational.'
            response.intent = 'STATUS_REPORT'
            response.confidence = 0.9
            response.suggested_actions = ['speak']
            return response

        response.answer = f'I heard your command: {q}. Standing by for instructions.'
        response.intent = 'GENERAL_QUERY'
        response.confidence = 0.7
        response.suggested_actions = ['speak']
        return response


def main(args=None):
    rclpy.init(args=args)
    node = LLMReasoningNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
