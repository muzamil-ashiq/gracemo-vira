#!/usr/bin/env python3
"""
GraceEMO — Voice Interaction & Speech Synthesis Node
Listens for voice commands, manages spoken text-to-speech outputs,
and bridges audio interaction to the GraceEMO AI Brain.
"""

import time
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

try:
    from gracemo_interfaces.msg import VoiceCommand
    HAVE_INTERFACES = True
except ImportError:
    HAVE_INTERFACES = False

class DialogueVoiceNode(Node):
    def __init__(self):
        super().__init__('dialogue_node')
        self.get_logger().info('🎙️ Initializing GraceEMO Natural Voice & Dialogue Pipeline...')

        self.declare_parameter('wake_word', 'hey gracemo')
        self.wake_word = self.get_parameter('wake_word').value

        # Subscriptions
        self.say_sub = self.create_subscription(String, '/gracemo/say', self.on_say_text, 10)
        self.cmd_input_sub = self.create_subscription(String, '/gracemo/speech_input', self.on_speech_input, 10)

        # Publications
        self.spoken_pub = self.create_publisher(String, '/gracemo/spoken_text', 10)
        if HAVE_INTERFACES:
            self.voice_cmd_pub = self.create_publisher(VoiceCommand, '/gracemo/voice_command', 10)

        self.get_logger().info(f'👂 Listening for wake word: "{self.wake_word}"')
        self.get_logger().info('🔊 Text-to-Speech Engine Online on /gracemo/say')

    def on_say_text(self, msg: String):
        text = msg.data.strip()
        if not text:
            return
        self.get_logger().info(f'🤖 GraceEMO Speaking: "{text}"')
        
        # Publish to spoken_text stream for UI / telemetry
        out = String()
        out.data = text
        self.spoken_pub.publish(out)

    def on_speech_input(self, msg: String):
        transcript = msg.data.strip()
        self.get_logger().info(f'🗣️ Heard User: "{transcript}"')

        if HAVE_INTERFACES:
            cmd = VoiceCommand()
            cmd.transcript = transcript
            cmd.confidence = 0.95
            low = transcript.lower()
            if any(w in low for w in ('stop', 'halt', 'freeze')):
                cmd.intent = 'STOP'
            elif 'go to' in low or 'navigate' in low or 'take me' in low:
                cmd.intent = 'NAVIGATE'
            elif '?' in transcript or 'what' in low or 'who' in low:
                cmd.intent = 'QUERY'
            else:
                cmd.intent = 'COMMAND'
            cmd.entities = transcript.split()
            cmd.audio_duration = 2.5
            self.voice_cmd_pub.publish(cmd)

def main(args=None):
    rclpy.init(args=args)
    node = DialogueVoiceNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
