"""Tests for the model client. No Ollama and no network needed."""

import unittest

from pet_brain import OllamaBrain, clean


class TestClean(unittest.TestCase):
    def test_keeps_one_sentence(self):
        self.assertEqual(clean("Meow. That sounds hard. I will nap now."),
                         "Meow.")

    def test_strips_quotes_and_newlines(self):
        self.assertEqual(clean('"Woof!\nGood job"'), "Woof!")

    def test_truncates_a_long_ramble(self):
        long = " ".join(["word"] * 40)
        self.assertLessEqual(len(clean(long).split()), 20)

    def test_drops_stage_directions(self):
        self.assertEqual(clean("*purrs softly* Meow, I hear you."),
                         "Meow, I hear you.")

    def test_empty_becomes_none(self):
        self.assertIsNone(clean("   "))


class TestBrain(unittest.TestCase):
    def test_prompt_includes_history_and_new_line(self):
        brain = OllamaBrain()
        prompt = brain.build_prompt("I had an exam",
                                    [("hello", "Meow."), ("tired", "Purr.")])
        self.assertIn("hello", prompt)
        self.assertIn("Purr.", prompt)
        self.assertTrue(prompt.rstrip().endswith("You:"))

    def test_reply_returns_none_when_the_server_is_down(self):
        brain = OllamaBrain(url="http://127.0.0.1:1", timeout=0.2)
        self.assertIsNone(brain.reply("cat", "hello", []))

    def test_available_is_false_when_the_server_is_down(self):
        self.assertFalse(OllamaBrain(url="http://127.0.0.1:1").available())

    def test_reply_uses_the_model_response(self):
        brain = OllamaBrain()
        brain._post = lambda path, payload: {"response": "Meow. I hear you."}
        self.assertEqual(brain.reply("cat", "hi", []), "Meow.")

    def test_persona_and_history_reach_the_request(self):
        brain = OllamaBrain()
        seen = {}

        def fake_post(path, payload):
            seen.update(payload)
            return {"response": "Woof!"}

        brain._post = fake_post
        brain.reply("dog", "I passed my exam", [("hi", "Woof!")])
        self.assertIn("Buddy", seen["system"])
        self.assertIn("I passed my exam", seen["prompt"])
        self.assertEqual(seen["options"]["num_predict"], brain.max_tokens)


if __name__ == "__main__":
    unittest.main()
