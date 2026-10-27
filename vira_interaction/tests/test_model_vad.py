"""
GraceEMO Interaction — Model & VAD Engine Unit Tests
Tests the dynamic VAD state machine, noise floor adaptation, threshold scaling,
filtering logic, sensitivity adjustment, and manual controls.
"""
import unittest
import sys
import os
import numpy as np
import math

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import model


class TestDynamicVAD(unittest.TestCase):
    """Tests dynamic VAD math, threshold calculations, and state transitions."""

    def setUp(self):
        # Reset VAD state before each test
        model.B_T = 800.0
        model.B_T_INITIALIZED = True
        model.VOICE_FLAG = False
        model.VOICE_FRAMES_COUNT = 0
        model.SILENCE_FRAMES_COUNT = 0
        model.SESSION_VOICE_FRAMES = 0
        model.END_OF_RECORD = False
        model.LISTENING_ENABLED = True
        model.STOP_RECORDING = False
        model.NEXT_EXP = "idle"
        model.R_MIN = 0.15
        model.R_MAX = 0.60
        model.T_MIN = 2200.0

    def test_ambient_noise_ema_adaptation(self):
        """Ambient noise B_t adapts toward low audio energy when idle."""
        initial_bt = model.B_T
        # Generate low energy noise chunk (e.g., RMS ~ 500)
        low_noise = np.random.normal(0, 500, 2048).astype(np.int16)
        model.voice_switch(low_noise)
        # B_t should decrease toward 500
        self.assertLess(model.B_T, initial_bt)
        self.assertFalse(model.VOICE_FLAG)

    def test_speech_onset_detection(self):
        """Energy exceeding T_start for MIN_SPEECH_FRAMES triggers speech onset."""
        loud_chunk = np.random.normal(0, 6000, 2048).astype(np.int16)

        # Frame 1: energy above T_start, count increments to 1 (< MIN_SPEECH_FRAMES)
        model.voice_switch(loud_chunk)
        self.assertEqual(model.VOICE_FRAMES_COUNT, 1)
        self.assertFalse(model.VOICE_FLAG)

        # Frame 2: count increments to 2 (>= MIN_SPEECH_FRAMES), speech onset triggers
        model.voice_switch(loud_chunk)
        self.assertTrue(model.VOICE_FLAG)
        self.assertEqual(model.NEXT_EXP, "focus")
        self.assertFalse(model.END_OF_RECORD)

    def test_speech_continuation_and_silence_timeout(self):
        """Speech sustains while E_t > T_continue, ends when silence reaches END_OF_SPEECH_FRAMES."""
        loud_chunk = np.random.normal(0, 6000, 2048).astype(np.int16)
        silent_chunk = np.zeros(2048, dtype=np.int16)

        # Trigger speech onset (2 frames)
        model.voice_switch(loud_chunk)
        model.voice_switch(loud_chunk)
        self.assertTrue(model.VOICE_FLAG)

        # Sustain speech with 3 more loud frames
        for _ in range(3):
            model.voice_switch(loud_chunk)
            self.assertTrue(model.VOICE_FLAG)

        # Feed silence frames until END_OF_SPEECH_FRAMES is reached
        for i in range(model.END_OF_SPEECH_FRAMES):
            model.voice_switch(silent_chunk)
            if i < model.END_OF_SPEECH_FRAMES - 1:
                self.assertTrue(model.VOICE_FLAG)

        # After END_OF_SPEECH_FRAMES silence frames, recording ends
        self.assertFalse(model.VOICE_FLAG)
        self.assertTrue(model.END_OF_RECORD)
        self.assertEqual(model.NEXT_EXP, "idle")

    def test_short_speech_detection_count(self):
        """Verify session voice frames count correctly tracks voiced chunks."""
        loud_chunk = np.random.normal(0, 5000, 2048).astype(np.int16)
        silent_chunk = np.zeros(2048, dtype=np.int16)

        # Onset (2 frames) = 2 voiced frames
        model.voice_switch(loud_chunk)
        model.voice_switch(loud_chunk)
        self.assertEqual(model.SESSION_VOICE_FRAMES, 2)

        # Now silence until end of recording
        for _ in range(model.END_OF_SPEECH_FRAMES):
            model.voice_switch(silent_chunk)

        # 2 voiced chunks is below MIN_TOTAL_VOICE_FRAMES (3)
        self.assertLess(model.SESSION_VOICE_FRAMES, model.MIN_TOTAL_VOICE_FRAMES)


class TestSensitivityControls(unittest.TestCase):
    """Tests sensitivity adjustment [+] / [-] bounds and behavior."""

    def setUp(self):
        model.R_MIN = 0.15
        model.R_MAX = 0.60
        model.T_MIN = 2200.0

    def test_increase_strictness(self):
        """[+] increases r_min, r_max, and T_min."""
        model.adjust_threshold(+0.05, +200)
        self.assertAlmostEqual(model.R_MIN, 0.20, places=2)
        self.assertAlmostEqual(model.R_MAX, 0.65, places=2)
        self.assertEqual(model.T_MIN, 2400.0)

    def test_decrease_strictness(self):
        """[-] decreases r_min, r_max, and T_min."""
        model.adjust_threshold(-0.05, -200)
        self.assertAlmostEqual(model.R_MIN, 0.10, places=2)
        self.assertAlmostEqual(model.R_MAX, 0.55, places=2)
        self.assertEqual(model.T_MIN, 2000.0)

    def test_clipping_bounds(self):
        """Bounds clipping prevents sensitivity parameters from going out of range."""
        for _ in range(20):
            model.adjust_threshold(+0.10, +500)
        self.assertLessEqual(model.R_MIN, 0.50)
        self.assertLessEqual(model.R_MAX, 0.90)

        for _ in range(40):
            model.adjust_threshold(-0.10, -500)
        self.assertGreaterEqual(model.R_MIN, 0.05)
        self.assertGreaterEqual(model.R_MAX, 0.25)
        self.assertGreaterEqual(model.T_MIN, 800.0)


class TestManualControls(unittest.TestCase):
    """Tests manual listening keyboard controls 's' and 'e'."""

    def test_stop_and_start_controls(self):
        """'e' stops listening; 's' resumes listening."""
        model.LISTENING_ENABLED = True
        model.STOP_RECORDING = False

        # Simulate pressing 'e'
        stop_key = type("Key", (), {"char": "e"})()
        model.on_press(stop_key)
        self.assertFalse(model.LISTENING_ENABLED)
        self.assertTrue(model.STOP_RECORDING)

        # Pressing 'e' again while stopped changes nothing
        model.on_press(stop_key)
        self.assertFalse(model.LISTENING_ENABLED)
        self.assertTrue(model.STOP_RECORDING)

        # Simulate pressing 's' when stopped
        start_key = type("Key", (), {"char": "s"})()
        # Mock record_audio thread so it doesn't open real hardware during test
        model.IS_RECORDING = False
        model.on_press(start_key)
        self.assertTrue(model.LISTENING_ENABLED)
        self.assertFalse(model.STOP_RECORDING)


class TestSpeechFilteringAndNormalization(unittest.TestCase):
    """Tests Whisper hallucination detection, deduplication, and phonetics."""

    def test_hallucination_filtering(self):
        """Ghost phrases and silence hallucinations are identified."""
        self.assertTrue(model.is_hallucination_or_noise(""))
        self.assertTrue(model.is_hallucination_or_noise("a"))
        self.assertTrue(model.is_hallucination_or_noise("you"))
        self.assertTrue(model.is_hallucination_or_noise("thank you."))
        self.assertTrue(model.is_hallucination_or_noise("thanks for watching"))
        self.assertTrue(model.is_hallucination_or_noise("subtitles by amara.org"))
        self.assertFalse(model.is_hallucination_or_noise("Where is the robotics research lab?"))

    def test_speech_deduplication(self):
        """Repeated sentences and acoustic starter words are cleaned."""
        raw = "Hello robot. Hello robot. Hello robot."
        cleaned = model.clean_and_deduplicate_speech(raw)
        self.assertEqual(cleaned, "Hello robot.")

        raw_starter = "Um, where is the library?"
        cleaned_starter = model.clean_and_deduplicate_speech(raw_starter)
        self.assertEqual(cleaned_starter, "where is the library?")

    def test_expression_extraction(self):
        """<exp-*> tokens are parsed and set to NEXT_EXP."""
        text = "Welcome to campus! <exp-happy>"
        clean = model.extract_and_apply_exp(text)
        self.assertEqual(clean, "Welcome to campus!")
        self.assertEqual(model.NEXT_EXP, "happy")

    def test_phonetic_speech_normalization(self):
        """Acronyms and titles are phonetically expanded for TTS clarity."""
        text = "Welcome! Meeting with Dr. Ashok Mittal and VC Prof. Sandhu at Pro-VC office."
        normalized = model.phonetic_speech_normalize(text)
        self.assertIn("Doctor Ashok Mittal", normalized)
        self.assertIn("Vice Chancellor", normalized)
        self.assertIn("Professor", normalized)
        self.assertIn("Pro Vice-Chancellor", normalized)

    def test_campus_place_extraction(self):
        """Campus place keywords map to authoritative location names."""
        self.assertEqual(model.extract_campus_place("take me to the lab"), "Robotics Research Lab")
        self.assertEqual(model.extract_campus_place("where is the library?"), "Central Library (B37)")
        self.assertEqual(model.extract_campus_place("go to the uni-mall"), "Uni-Mall Shopping Center")


class TestEssentialAssetsIntegrity(unittest.TestCase):
    """Validates that all essential directories, config files, and expression videos exist."""

    def test_configuration_files(self):
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.assertTrue(os.path.exists(os.path.join(base, "config", "places.json")))
        self.assertTrue(os.path.exists(os.path.join(base, "font.ttf")))
        self.assertTrue(os.path.exists(os.path.join(base, "data", "human_memory.json")))

    def test_knowledge_files(self):
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        data_dir = os.path.join(base, "data")
        txt_files = [f for f in os.listdir(data_dir) if f.endswith(".txt")]
        self.assertEqual(len(txt_files), 10)

    def test_facial_expression_videos(self):
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        vid_dir = os.path.join(base, "vid")
        self.assertTrue(os.path.isdir(vid_dir))
        folders = [f for f in os.listdir(vid_dir) if os.path.isdir(os.path.join(vid_dir, f))]
        self.assertGreaterEqual(len(folders), 36)
        for folder in folders:
            vids = [v for v in os.listdir(os.path.join(vid_dir, folder)) if v.endswith((".mkv", ".mp4", ".avi"))]
            self.assertGreater(len(vids), 0, f"Expression folder {folder} contains no video files")


class TestVADReliabilityPatch(unittest.TestCase):
    """
    Focused regression tests for VAD reliability, numerical stability,
    configuration validation, and active sensitivity adjustments.
    """

    def setUp(self):
        # Reset VAD state and default parameters
        model.B_T = 800.0
        model.B_T_INITIALIZED = True
        model.VOICE_FLAG = False
        model.VOICE_FRAMES_COUNT = 0
        model.SILENCE_FRAMES_COUNT = 0
        model.SESSION_VOICE_FRAMES = 0
        model.END_OF_RECORD = False
        model.LISTENING_ENABLED = True
        model.STOP_RECORDING = False
        model.NEXT_EXP = "idle"
        model.R_MIN = 0.15
        model.R_MAX = 0.60
        model.T_MIN = 1500.0
        model.T_MIN_MIN = 800.0
        model.T_MIN_MAX = 6000.0
        model.B_T_MIN = 200.0
        model.ADAPT_K = 0.45
        model.HYSTERESIS_BETA = 0.45
        model.DELTA_MIN = 800.0

    def test_empty_audio_buffers(self):
        """1. Empty buffers or None do not throw, return safe energy, and preserve ambient estimate."""
        initial_bt = model.B_T

        # Test None buffer
        e_none, t_start1, t_cont1 = model.voice_switch(None)
        self.assertEqual(e_none, 0.0)
        self.assertEqual(model.B_T, initial_bt)
        self.assertFalse(model.VOICE_FLAG)

        # Test empty numpy array
        empty_arr = np.array([], dtype=np.int16)
        e_empty, t_start2, t_cont2 = model.voice_switch(empty_arr)
        self.assertEqual(e_empty, 0.0)
        self.assertEqual(model.B_T, initial_bt)
        self.assertFalse(model.VOICE_FLAG)

    def test_nan_and_infinite_samples(self):
        """2. Buffers containing NaN or Inf do not contaminate B_t or crash."""
        initial_bt = model.B_T

        # Array with NaN
        nan_arr = np.array([np.nan, 500.0, 300.0], dtype=np.float32)
        e_nan, _, _ = model.voice_switch(nan_arr)
        self.assertEqual(e_nan, 0.0)
        self.assertEqual(model.B_T, initial_bt)
        self.assertTrue(math.isfinite(model.B_T))

        # Array with +inf and -inf
        inf_arr = np.array([np.inf, -np.inf, 200.0], dtype=np.float32)
        e_inf, _, _ = model.voice_switch(inf_arr)
        self.assertEqual(e_inf, 0.0)
        self.assertEqual(model.B_T, initial_bt)
        self.assertTrue(math.isfinite(model.B_T))

    def test_zero_energy_over_prolonged_idle(self):
        """3. Prolonged zero-energy frames decay ambient noise to B_T_MIN (200.0), never below."""
        model.B_T = 1000.0
        zero_chunk = np.zeros(2048, dtype=np.int16)

        # Feed 200 consecutive idle frames (~26 seconds of digital silence)
        for _ in range(200):
            model.voice_switch(zero_chunk)

        # B_T must be strictly bounded by B_T_MIN (200.0)
        self.assertGreaterEqual(model.B_T, model.B_T_MIN)
        self.assertAlmostEqual(model.B_T, 200.0, delta=1.0)

    def test_invalid_configuration_values(self):
        """4. validate_vad_config raises ValueError for non-positive, out-of-order, or non-finite values."""
        # DELTA_MIN <= 0
        with self.assertRaises(ValueError):
            model.validate_vad_config(delta_min=0.0, t_min=1500.0, r_min=0.15, r_max=0.60, hysteresis_beta=0.45, adapt_k=0.45)
        with self.assertRaises(ValueError):
            model.validate_vad_config(delta_min=-100.0, t_min=1500.0, r_min=0.15, r_max=0.60, hysteresis_beta=0.45, adapt_k=0.45)

        # T_MIN <= 0
        with self.assertRaises(ValueError):
            model.validate_vad_config(delta_min=800.0, t_min=0.0, r_min=0.15, r_max=0.60, hysteresis_beta=0.45, adapt_k=0.45)

        # R_MIN > R_MAX
        with self.assertRaises(ValueError):
            model.validate_vad_config(delta_min=800.0, t_min=1500.0, r_min=0.70, r_max=0.50, hysteresis_beta=0.45, adapt_k=0.45)

        # HYSTERESIS_BETA >= 1.0 or < 0
        with self.assertRaises(ValueError):
            model.validate_vad_config(delta_min=800.0, t_min=1500.0, r_min=0.15, r_max=0.60, hysteresis_beta=1.2, adapt_k=0.45)
        with self.assertRaises(ValueError):
            model.validate_vad_config(delta_min=800.0, t_min=1500.0, r_min=0.15, r_max=0.60, hysteresis_beta=-0.1, adapt_k=0.45)

        # ADAPT_K < 0
        with self.assertRaises(ValueError):
            model.validate_vad_config(delta_min=800.0, t_min=1500.0, r_min=0.15, r_max=0.60, hysteresis_beta=0.45, adapt_k=-0.5)

        # NaN / Inf parameters
        with self.assertRaises(ValueError):
            model.validate_vad_config(delta_min=float('nan'), t_min=1500.0, r_min=0.15, r_max=0.60, hysteresis_beta=0.45, adapt_k=0.45)
        with self.assertRaises(ValueError):
            model.validate_vad_config(delta_min=800.0, t_min=float('inf'), r_min=0.15, r_max=0.60, hysteresis_beta=0.45, adapt_k=0.45)

    def test_continuation_threshold_not_exceeding_start(self):
        """5. T_continue is strictly less than or equal to T_start across various ambient and parameter configs."""
        test_bt_values = [200.0, 500.0, 1000.0, 3000.0, 8000.0]
        test_t_min_values = [800.0, 1500.0, 3000.0, 6000.0]

        for bt in test_bt_values:
            for t_min in test_t_min_values:
                model.B_T = bt
                model.T_MIN = t_min
                t_start, t_cont, _, _ = model.compute_vad_thresholds(bt)
                self.assertLessEqual(t_cont, t_start, f"T_continue ({t_cont}) exceeded T_start ({t_start}) for B_t={bt}, T_min={t_min}")

    def test_thresh_cli_changes_active_vad_setting(self):
        """6. thresh CLI command updates active R_MIN and R_MAX, which actively influences compute_vad_thresholds."""
        model.set_threshold_ratio(0.15)
        self.assertEqual(model.R_MIN, 0.15)
        t_start_init, _, r_t_init, _ = model.compute_vad_thresholds(3000.0)

        # Set higher ratio via CLI
        success = model.handle_thresh_cli("0.35")
        self.assertTrue(success)
        self.assertAlmostEqual(model.R_MIN, 0.35, places=2)
        self.assertAlmostEqual(model.R_MAX, 0.80, places=2)

        # Verify that the new ratio actively increased r_t and T_start
        t_start_new, _, r_t_new, _ = model.compute_vad_thresholds(3000.0)
        self.assertGreater(r_t_new, r_t_init)
        self.assertGreater(t_start_new, t_start_init)

    def test_rejection_of_invalid_cli_values(self):
        """7. handle_thresh_cli rejects NaN, Inf, non-numeric strings, and out-of-bound values without modifying R_MIN."""
        model.set_threshold_ratio(0.20)
        current_rmin = model.R_MIN

        invalid_inputs = ["nan", "NaN", "inf", "-inf", "abc", "0.01", "0.55", "-0.1", "100.0", "", None]
        for bad_val in invalid_inputs:
            result = model.handle_thresh_cli(bad_val)
            self.assertFalse(result, f"Expected rejection for input '{bad_val}'")
            self.assertEqual(model.R_MIN, current_rmin, f"R_MIN was modified on rejected input '{bad_val}'")

    def test_manual_adjustment_bounds(self):
        """8. adjust_threshold enforces T_MIN ceiling (6000.0), floor (800.0), and ratio bounds."""
        model.R_MIN = 0.15
        model.R_MAX = 0.60
        model.T_MIN = 1500.0

        # Repeatedly increase 50 times
        for _ in range(50):
            model.adjust_threshold(+0.05, +200)

        self.assertLessEqual(model.T_MIN, model.T_MIN_MAX)
        self.assertEqual(model.T_MIN, 6000.0)
        self.assertEqual(model.R_MIN, 0.50)
        self.assertEqual(model.R_MAX, 0.90)

        # Repeatedly decrease 50 times
        for _ in range(50):
            model.adjust_threshold(-0.05, -200)

        self.assertGreaterEqual(model.T_MIN, model.T_MIN_MIN)
        self.assertEqual(model.T_MIN, 800.0)
        self.assertEqual(model.R_MIN, 0.05)
        self.assertEqual(model.R_MAX, 0.25)

    def test_normal_speech_onset_and_end_preserved(self):
        """9. Valid speech buffers trigger speech onset at frame 2, and silence triggers speech end after 11 frames."""
        loud_chunk = np.random.normal(0, 5000, 2048).astype(np.int16)
        silent_chunk = np.zeros(2048, dtype=np.int16)

        # Frame 1: count becomes 1 (< 2 frames), VOICE_FLAG remains False
        model.voice_switch(loud_chunk)
        self.assertEqual(model.VOICE_FRAMES_COUNT, 1)
        self.assertFalse(model.VOICE_FLAG)

        # Frame 2: count becomes 2 (>= MIN_SPEECH_FRAMES), speech onset triggers
        model.voice_switch(loud_chunk)
        self.assertTrue(model.VOICE_FLAG)
        self.assertEqual(model.NEXT_EXP, "focus")

        # 11 frames of silence -> Speech end triggers
        for _ in range(model.END_OF_SPEECH_FRAMES):
            model.voice_switch(silent_chunk)

        self.assertFalse(model.VOICE_FLAG)
        self.assertTrue(model.END_OF_RECORD)
        self.assertEqual(model.NEXT_EXP, "idle")


if __name__ == "__main__":
    unittest.main()
