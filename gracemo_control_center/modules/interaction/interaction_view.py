"""
Module 6: Voice & Interaction Center for GRaCEmo ViRa UARCC.
Monitors Whisper live speech recognition, spoken TTS responses,
natural language intent grounding, and conversation history without duplicate audio capture.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QFrame, QPushButton, QLineEdit, QTextEdit, QScrollArea
)
from PySide6.QtCore import Qt, QDateTime
from PySide6.QtGui import QFont

import time
import json

from ...resources.styles.tokens import (
    COLOR_BG_MAIN,
    COLOR_SURFACE,
    COLOR_PANEL_MAIN,
    COLOR_PANEL_SECONDARY,
    COLOR_BORDER,
    COLOR_BORDER_LIGHT,
    COLOR_BRAND_ORANGE,
    COLOR_ACCENT_PRIMARY,
    COLOR_SUCCESS,
    COLOR_WARNING,
    COLOR_ERROR,
    COLOR_INFO,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_MUTED,
    FONT_FAMILY_PRIMARY,
    FONT_FAMILY_MONO,
    BORDER_RADIUS_SM,
    BORDER_RADIUS_MD,
)
from ...widgets.status_indicator import StatusIndicator
from ...widgets.common_components import PageHeader, SectionHeader, MetricDisplay
from ...core.event_bus import bus


class InteractionView(QWidget):
    """Module 6: Voice and Human-Robot Interaction Monitoring Center."""

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # 1. Page Header
        self.header = PageHeader(
            title="Voice & Interaction",
            subtitle="Whisper STT, spoken dialogue responses, natural language intent grounding, and text commands",
            badge_title="Voice Engine",
            initial_state=StatusIndicator.STATE_NOT_CONNECTED,
            target_page="Voice & Interaction",
            parent=self
        )
        self.ind_voice_engine = self.header.badge
        layout.addWidget(self.header)

        # 2. Pipeline State Indicator Card
        state_card = QFrame(self)
        state_card.setProperty("class", "cardPanel")
        s_layout = QVBoxLayout(state_card)
        s_layout.setSpacing(10)

        s_hdr = SectionHeader("Interaction Engine Pipeline Stages", parent=self)
        s_layout.addWidget(s_hdr)

        pipeline_row = QHBoxLayout()
        pipeline_row.setSpacing(10)

        self.ind_stt = StatusIndicator("Whisper STT", StatusIndicator.STATE_READY)
        self.ind_intent = StatusIndicator("Intent Parser", StatusIndicator.STATE_READY)
        self.ind_grounding = StatusIndicator("Place Grounding", StatusIndicator.STATE_READY)
        self.ind_tts = StatusIndicator("Spoken TTS", StatusIndicator.STATE_READY)

        for ind in (self.ind_stt, self.ind_intent, self.ind_grounding, self.ind_tts):
            pipeline_row.addWidget(ind)
        pipeline_row.addStretch()

        s_layout.addLayout(pipeline_row)
        layout.addWidget(state_card)

        # 3. Conversation & Speech Event History Card
        conv_card = QFrame(self)
        conv_card.setProperty("class", "cardPanel")
        c_layout = QVBoxLayout(conv_card)
        c_layout.setSpacing(12)

        c_hdr = SectionHeader("Dialogue History & Live Utterance Stream", parent=self)
        c_layout.addWidget(c_hdr)

        self.txt_conversation = QTextEdit(self)
        self.txt_conversation.setReadOnly(True)
        self.txt_conversation.setStyleSheet(f"""
            QTextEdit {{
                background-color: {COLOR_PANEL_SECONDARY};
                border: 1px solid {COLOR_BORDER};
                border-radius: {BORDER_RADIUS_SM}px;
                color: {COLOR_TEXT_PRIMARY};
                font-family: {FONT_FAMILY_PRIMARY};
                font-size: 13px;
                line-height: 1.5;
                padding: 10px;
            }}
        """)
        c_layout.addWidget(self.txt_conversation, stretch=1)

        # 4. Text Command Dispatch Bar
        input_row = QHBoxLayout()
        input_row.setSpacing(10)

        self.input_text = QLineEdit(self)
        self.input_text.setPlaceholderText("Type a command or query (e.g., 'navigate to living room', 'what is your status')...")
        self.input_text.returnPressed.connect(self._send_text_command)
        input_row.addWidget(self.input_text, stretch=4)

        self.btn_send = QPushButton("Send Command", self)
        self.btn_send.setProperty("class", "primaryButton")
        self.btn_send.clicked.connect(self._send_text_command)
        input_row.addWidget(self.btn_send, stretch=1)

        c_layout.addLayout(input_row)
        layout.addWidget(conv_card, stretch=1)

        # Connect signals
        bus.user_input_received.connect(self._on_user_input)
        bus.voice_recognized.connect(self._on_voice_recognized)
        bus.spoken_feedback_received.connect(self._on_spoken_feedback)

    def _on_user_input(self, text: str, source: str):
        self.ind_voice_engine.set_state(StatusIndicator.STATE_READY)
        ts = QDateTime.currentDateTime().toString("hh:mm:ss")
        self.txt_conversation.append(f"<span style='color:{COLOR_ACCENT_PRIMARY}; font-weight: 600;'>[{ts}] 👤 USER ({source}):</span> {text}")

    def _on_voice_recognized(self, text: str):
        self.ind_voice_engine.set_state(StatusIndicator.STATE_READY)
        ts = QDateTime.currentDateTime().toString("hh:mm:ss")
        self.txt_conversation.append(f"<span style='color:{COLOR_BRAND_ORANGE}; font-weight: 600;'>[{ts}] 🎙️ WHISPER LIVE RECOGNIZED:</span> <i>\"{text}\"</i>")

    def _on_spoken_feedback(self, text: str, status: str):
        ts = QDateTime.currentDateTime().toString("hh:mm:ss")
        self.txt_conversation.append(f"<span style='color:{COLOR_SUCCESS}; font-weight: 600;'>[{ts}] 🤖 GRaCEmo ({status}):</span> {text}")

    def _send_text_command(self):
        text = self.input_text.text().strip()
        if not text:
            return
        self.input_text.clear()
        bus.user_input_received.emit(text, "DESKTOP_GUI")
