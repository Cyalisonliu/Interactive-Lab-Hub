"""Tests for the Chatterbox state machine (no Pi hardware needed)."""

import unittest

from pet_logic import ANIMALS, PetMachine


class TestStart(unittest.TestCase):
    def test_starts_asleep_and_says_nothing(self):
        m = PetMachine()
        self.assertEqual(m.state, "ASLEEP")
        self.assertEqual(m.led, "off")
        self.assertIn("Press to start", m.screen)

    def test_speech_is_ignored_while_asleep(self):
        m = PetMachine()
        r = m.hear("cat")
        self.assertIsNone(r.say)
        self.assertEqual(m.state, "ASLEEP")

    def test_button_opens_the_choose_screen(self):
        m = PetMachine()
        r = m.press()
        self.assertEqual(m.state, "CHOOSE")
        self.assertEqual(r.say, "Pick a friend: cat, dog, or bird.")
        self.assertEqual(m.led, "green")
        for name in ANIMALS:
            self.assertIn(name, m.screen)


class TestChoosing(unittest.TestCase):
    def setUp(self):
        self.m = PetMachine()
        self.m.press()

    def test_keyword_anywhere_in_the_sentence_counts(self):
        r = self.m.hear("um, I want the dog please")
        self.assertEqual(self.m.animal, "dog")
        self.assertIn("Buddy", r.say)
        self.assertEqual(self.m.state, "CONVERSE")

    def test_button_picks_the_next_animal_without_speech(self):
        r = self.m.press()
        self.assertEqual(self.m.animal, "cat")
        self.assertIn("Mochi", r.say)
        r = self.m.press()
        self.assertEqual(self.m.animal, "dog")

    def test_three_failures_go_back_to_sleep(self):
        first = self.m.hear("hat")
        self.assertEqual(first.say, "Please say cat, dog, or bird.")
        second = self.m.hear("hat")
        self.assertIn("press the button", second.say)
        third = self.m.hear("hat")
        self.assertIn("Press to start", third.say)
        self.assertEqual(self.m.state, "ASLEEP")
        self.assertEqual(self.m.led, "off")

    def test_silence_counts_toward_the_same_three_tries(self):
        self.m.nothing_heard()
        self.m.hear("hat")
        third = self.m.nothing_heard()
        self.assertIn("Press to start", third.say)
        self.assertEqual(self.m.state, "ASLEEP")

    def test_a_success_resets_the_failure_count(self):
        self.m.hear("hat")
        self.m.hear("cat")
        self.assertEqual(self.m.state, "CONVERSE")
        self.assertEqual(self.m.tries, 0)


class TestConversation(unittest.TestCase):
    def talk_to(self, animal):
        m = PetMachine()
        m.press()
        m.hear(animal)
        return m

    def test_keyword_replies(self):
        m = self.talk_to("cat")
        self.assertEqual(m.hear("it was good").say, "I'm glad to hear that!")
        self.assertEqual(m.hear("kind of tiring").say, "You should take a little rest.")
        self.assertEqual(m.hear("yes").say, "Yay!")
        self.assertEqual(m.hear("no").say, "That's okay.")

    def test_bye_ends_and_sleeps(self):
        m = self.talk_to("dog")
        r = m.hear("bye")
        self.assertIn("Bye", r.say)
        self.assertEqual(m.state, "ASLEEP")
        self.assertEqual(m.led, "off")

    def test_unknown_answer_is_re_prompted_then_sleeps(self):
        m = self.talk_to("cat")
        self.assertIn("say good, tiring", m.hear("purple elephant").say)
        m.hear("purple elephant")
        third = m.hear("purple elephant")
        self.assertIn("Press to start", third.say)
        self.assertEqual(m.state, "ASLEEP")

    def test_bird_repeats_any_word_instead_of_re_prompting(self):
        m = self.talk_to("bird")
        r = m.hear("banana")
        self.assertEqual(r.say, "Tweet! banana!")
        self.assertEqual(m.state, "CONVERSE")
        self.assertEqual(m.tries, 0)

    def test_bird_still_obeys_bye(self):
        m = self.talk_to("bird")
        r = m.hear("bye")
        self.assertIn("Bye", r.say)
        self.assertEqual(m.state, "ASLEEP")

    def test_button_switches_friend_mid_conversation(self):
        m = self.talk_to("cat")
        r = m.press()
        self.assertEqual(m.animal, "dog")
        self.assertIn("Buddy", r.say)
        self.assertEqual(m.state, "CONVERSE")

    def test_button_wraps_around_from_bird_to_cat(self):
        m = self.talk_to("bird")
        m.press()
        self.assertEqual(m.animal, "cat")


class TestIndicators(unittest.TestCase):
    def test_led_colors_follow_the_turn(self):
        m = PetMachine()
        self.assertEqual(m.led, "off")
        m.press()
        self.assertEqual(m.led, "green")          # listening for an animal
        r = m.hear("cat")
        self.assertEqual(r.led, "blue")           # speaking its greeting
        self.assertEqual(m.led, "green")          # back to your turn afterwards

    def test_mishearing_is_shown_on_screen_too(self):
        m = PetMachine()
        m.press()
        r = m.hear("hat")
        self.assertIn("hat", r.heard_text)

    def test_screen_shows_what_was_heard(self):
        m = PetMachine()
        m.press()
        r = m.hear("cat")
        self.assertIn("cat", r.heard_text)


class FakeBrain:
    """Stands in for the local model so the tests stay fast and offline."""

    def __init__(self, reply="Purr, tell me more.", fail=False):
        self.reply_text = reply
        self.fail = fail
        self.calls = []

    def reply(self, animal, text, history):
        self.calls.append((animal, text, list(history)))
        if self.fail:
            return None          # model unreachable or too slow
        return self.reply_text


class TestFreeConversation(unittest.TestCase):
    def talk_to(self, animal, brain):
        m = PetMachine(brain=brain)
        m.press()
        m.hear(animal)
        return m

    def test_unknown_input_goes_to_the_brain(self):
        brain = FakeBrain("Meow, exams are hard.")
        m = self.talk_to("cat", brain)
        r = m.hear("I had an exam today")
        self.assertEqual(r.say, "Meow, exams are hard.")
        self.assertEqual(m.state, "CONVERSE")
        self.assertEqual(m.tries, 0)
        self.assertEqual(brain.calls[0][0], "cat")
        self.assertIn("exam", brain.calls[0][1])

    def test_keywords_still_answer_instantly_without_the_brain(self):
        brain = FakeBrain()
        m = self.talk_to("cat", brain)
        self.assertEqual(m.hear("good").say, "I'm glad to hear that!")
        self.assertEqual(brain.calls, [])

    def test_bye_still_ends_without_the_brain(self):
        brain = FakeBrain()
        m = self.talk_to("dog", brain)
        self.assertIn("Bye", m.hear("bye").say)
        self.assertEqual(m.state, "ASLEEP")
        self.assertEqual(brain.calls, [])

    def test_history_is_passed_so_replies_can_follow_on(self):
        brain = FakeBrain()
        m = self.talk_to("cat", brain)
        m.hear("I had an exam")
        m.hear("it went okay")
        self.assertTrue(len(brain.calls[1][2]) >= 1)

    def test_brain_failure_falls_back_to_a_fixed_line(self):
        brain = FakeBrain(fail=True)
        m = self.talk_to("cat", brain)
        r = m.hear("something unexpected")
        self.assertIsNotNone(r.say)
        self.assertEqual(m.state, "CONVERSE")

    def test_choosing_an_animal_never_uses_the_brain(self):
        brain = FakeBrain()
        m = PetMachine(brain=brain)
        m.press()
        m.hear("hat")
        self.assertEqual(brain.calls, [])


class TestKeywordsDoNotHijackSentences(unittest.TestCase):
    """Bugs seen on the Pi: 'I don't have a good day' answered as 'good'."""

    def talk_to(self, animal, brain=None):
        m = PetMachine(brain=brain)
        m.press()
        m.hear(animal)
        return m

    def test_long_sentence_with_a_keyword_goes_to_the_brain(self):
        brain = FakeBrain("Woof, that sounds rough.")
        m = self.talk_to("dog", brain)
        r = m.hear("I mean I don't have a good day")
        self.assertEqual(r.say, "Woof, that sounds rough.")
        self.assertEqual(len(brain.calls), 1)

    def test_negated_keyword_is_not_a_cheerful_answer(self):
        m = self.talk_to("dog")           # no brain: fixed lines only
        r = m.hear("not good")
        self.assertNotEqual(r.say, "I'm glad to hear that!")

    def test_plain_keyword_still_answers_instantly(self):
        brain = FakeBrain()
        m = self.talk_to("dog", brain)
        self.assertEqual(m.hear("good").say, "I'm glad to hear that!")
        self.assertEqual(m.hear("yes please").say, "Yay!")
        self.assertEqual(brain.calls, [])

    def test_no_is_still_its_own_answer(self):
        m = self.talk_to("cat")
        self.assertEqual(m.hear("no").say, "That's okay.")


class TestBrainKnowsTheQuestion(unittest.TestCase):
    def test_greeting_is_in_the_history_the_brain_sees(self):
        brain = FakeBrain()
        m = PetMachine(brain=brain)
        m.press()
        m.hear("dog")
        m.hear("not really")
        history = brain.calls[0][2]
        self.assertTrue(any("Did you have a good day?" in pet for _, pet in history))


if __name__ == "__main__":
    unittest.main()
