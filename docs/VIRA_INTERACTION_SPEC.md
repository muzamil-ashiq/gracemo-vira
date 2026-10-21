# GRaCEmo ViRa — Cognitive Interaction Specification
**Phase 1 Deliverable — Real-Time Robot Development Mode**  
**Document ID:** `VIRA-SPEC-P1-003`  
**System Version:** v0.0.3  

---

## 1. Interaction State Model

The robot's cognitive interaction lifecycle is governed by an **authoritative finite state machine (FSM)**. Cognitive state must **never** be conflated with facial emotions:
- **Cognitive State** dictates processing phase, input gating, and safety allowances.
- **Facial Expression** dictates visual avatar appearance on screen.

### 1.1 Cognitive FSM Transitions

```text
       ┌──────────┐
       │   BOOT   │
       └────┬─────┘
            │ self-test passed
            ▼
 ┌───────► IDLE ◄──────────────────────────────────────────────┐
 │          │                                                  │
 │          │ wake word / 's' key / energy spike               │
 │          ▼                                                  │
 │     LISTENING ───[silence timeout / 'e' key]──► THINKING    │
 │          ▲                                           │      │
 │          │ user barge-in                             │      │
 │          │                                           ▼      │
 │       SPEAKING ◄────[TTS synthesis ready]──── EXECUTING     │
 │          │                                           ▲      │
 │          │ speech playback finished                  │      │
 │          ▼                                           │      │
 │       WAITING ───[action dispatched to robot]────────┘      │
 │          │                                                  │
 │          └──────────► task complete / timeout ──────────────┘
 │
 ├───[Safety Violation / Exception]──► ERROR ──► RECOVERY ─────┤
 │
 └───[Emergency Stop Command]────────► EMERGENCY_STOP ─────────┘
```

### 1.2 State Matrix & Behavior

| State | Allowed Inputs | Visual Expression | Audio Hardware | Robot Motion Allowed | Next States |
| :--- | :--- | :--- | :--- | :---: | :--- |
| **`BOOT`** | None | `idle` | Calibrating | No | `IDLE`, `ERROR` |
| **`IDLE`** | VAD, Wake word, Key `s`, REST | `idle` | Passive listening | Yes | `LISTENING`, `EXECUTING` |
| **`LISTENING`** | Speech frames, Key `e` | `focus` | Recording active | Hold current | `THINKING`, `IDLE` |
| **`THINKING`** | Cancel key | `intent` | Processing STT/LLM | Hold current | `SPEAKING`, `EXECUTING`, `ERROR` |
| **`SPEAKING`** | Barge-in speech, STOP | Tagged (`happy`/`focus`) | TTS Playback | Yes | `WAITING`, `IDLE`, `LISTENING` |
| **`EXECUTING`** | Sensor telemetry, STOP | `focus` | Listening for STOP | Active | `WAITING`, `SPEAKING`, `ERROR` |
| **`WAITING`** | Robot arrival events, STOP | `idle` / `happy` | Listening for STOP | Active | `IDLE`, `SPEAKING` |
| **`ERROR`** | Diagnostics | `sad` | Silent / Error chime| Braked | `RECOVERY`, `IDLE` |
| **`RECOVERY`** | Automated reset | `intent` | Silent | Slow align | `IDLE`, `ERROR` |
| **`EMERGENCY_STOP`**| Manual reset command | `angry` | Immediate mute | Hard stop | `IDLE` |

---

## 2. Decoupled Emotional Expressions

The facial avatar renderer in [`graceemo_interaction/model.py`](file:///Users/samdavi/projects/VIRA/graceemo_interaction/model.py) renders 38 video transition clips across 6 expression states:

$$\text{Expressions} = \{\text{idle, happy, focus, sad, angry, intent}\}$$

A single interaction state can map to different expressions depending on dialogue sentiment and robotic feedback:
- `cognitive_state = EXECUTING` with `expression = focus` (while navigating through doorway)
- `cognitive_state = SPEAKING` with `expression = happy` (welcoming a student to LPU)
- `cognitive_state = WAITING` with `expression = intent` (awaiting live internet search result)
- `cognitive_state = EMERGENCY_STOP` with `expression = angry` (obstacle clearance fault)

---

## 3. Fast-Path vs Cognitive Brain Pipeline

```
                              USER SPEECH
                                   │
                                   ▼
                           DialogueEngine.parse()
                                   │
         ┌─────────────────────────┴─────────────────────────┐
         │                                                   │
  [Deterministic Match]                               [Ambiguous Query]
         │                                                   │
         ▼                                                   ▼
   Fast-Path Dispatch                                 Cognitive Brain
   • STOP      $\to$ cancel nav / zero vel            • Pull MNSE Context (/context)
   • GREET     $\to$ hand_hi / "Hello!"               • Qwen 2.5 3B MLX / Gemini
   • NAVIGATE  $\to$ lookup places.json               • Format: 1-2 lines + <exp-*>
         │                                                   │
         └─────────────────────────┬─────────────────────────┘
                                   │
                                   ▼
                            ActionRequested
                                   │
                                   ▼
                             Safety Gateway
```

### Fast-Path Intent Rules
1. **`STOP`**: Triggered by words `["stop", "halt", "freeze", "emergency", "wait"]`. Immediate zero-velocity published; cancels any active Nav2 goal.
2. **`GREET`**: Triggered by `["hello", "hi", "hey", "wave", "hand hi"]`. Dispatches `hand_hi` gesture and friendly welcome response.
3. **`NAVIGATE`**: Triggered by `["go to", "navigate", "take me", "drive to", "walk to"]`. Extracts location from [`places.json`](file:///Users/samdavi/projects/VIRA/graceemo_interaction/config/places.json) or apartment topology.

---

## 4. Persona & Grounding Directives

The Vice Chancellor persona is grounded via the modular knowledge files in [`graceemo_interaction/data/`](file:///Users/samdavi/projects/VIRA/graceemo_interaction/data):
- **Role**: Vice Chancellor and Executive Campus Ambassador of Lovely Professional University (LPU).
- **Tone**: Visionary, dignified, intellectually inspiring, supportive of research and student ambition.
- **Conciseness Protocol**: 1 to 2 spoken lines ($<40$ words).
- **Tagging Protocol**: Every LLM utterance must terminate with an emotion tag (`<exp-happy>`, `<exp-focus>`, `<exp-intent>`, `<exp-idle>`) and optional gesture tag (`{hand-hi}`, `{hand-up}`, `{hand-down}`).
- **Memory Consistency**: Integrates with [`human_memory.json`](file:///Users/samdavi/projects/VIRA/graceemo_interaction/data/human_memory.json) to recognize repeat visitors, creators (Sam Davi, John Allson, Sarvesh, Alex Matthew, Balamurugan), and faculty mentors (Dr. Mohit Arora).
