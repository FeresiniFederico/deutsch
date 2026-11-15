"""
Prompt templates used for Gemini LLM interactions.
"""


class Prompts:
    MARKER_SUMMARY = "--- ECCO IL RIASSUNTO ---"

    @staticmethod
    def audio_translation(context: str) -> str:
        """Prompt to translate Italian context into A2 German for audio review."""
        return f"""
*** Exercise Context (A2 German Level) ***
{context}

Task: Translate the Italian text contained in the context above into German, suitable for an A2 German learner.

CRITICAL INSTRUCTIONS:
- Return ONLY and EXCLUSIVELY the German translation.
- Do NOT include any introduction, greetings, explanations, notes, or concluding remarks.
- Do NOT add phrases like "Here is the translation" or markdown code blocks unless it's strictly the translated text itself.
- Keep it clean so it can be directly converted into a smooth audio message.
"""

    @staticmethod
    def daily_exercise(context: str, is_friday: bool) -> str:
        """Prompt to generate the daily German exercise. Friday includes summary expansion."""
        base_prompt = f"""
*** Context ***
{context}

Create a text of around 8 senteces in Italian for me to translate in German,
incorporating 70% of the words, verbs, and grammatical rules provided in the above context, 
and a 30% of new words. 
For the new words, provide a vocabulary at the end of the text structured as follows: 
 - German Word: Italian Translation

Try to use as many grammar rules described in the context as possible. 
Do not provide the translation, just focus on making the text relevant, with subordinates, 
using as many already seen words, verbs and grammar rules as possible.

The reply MUST be structured as follows:

"This is the Exercise to do:
<<TEXT IN ITALIAN>>"
-- Vocabulary --
<<LIST OF NEW WORDS WITH THEIR TRANSLATION>>"

Don't add anything else, keep it as simple as this.
"""
        if not is_friday:
            return base_prompt

        friday_extension = f"""
Furthermore, provide 2 additional sentences in German to be translated into Italian, containing new vocabularies, verbs,
and grammatical rules, each followed by a brief explanation in Italian of the new words and the new grammar rules that must be added to the final summary
to keep track of what we've learnt so far day by day. Keep all corrections and explanations very concise.
At the end, you MUST include the exact phrase "{Prompts.MARKER_SUMMARY}", followed solely by the context you would copy to provide an LLM to move on with exercises 
that precisely incorporate all previously learned vocabulary, verbs, and grammatical rules you already find in the provided context at the beginning of this prompt, 
along with the new additions.
Make sure to update the CONTEXT already provided, always starts from there, update that one, do not create a new one from scratch, just copy the same context and add the verbs and words and grammar rules you want me to learn. 
ALWAYS UPDATE THE PROVIDED CONTEXT!
"""
        return base_prompt + "\n" + friday_extension

    @staticmethod
    def flashcards(context: str) -> str:
        """Prompt to generate interactive spoiler flashcards."""
        return f"""
*** Learning Context (German A2 Level) ***
{context}

Task: Create 10 flashcards to review random words or verbs extracted ONLY from the context above.

STRICT FORMATTING INSTRUCTIONS:
- Return ONLY the 10 flashcards. No introduction, no conclusion.
- For each flashcard, write the visible prompt (e.g. the Italian word or German verb), followed by the hidden translation wrapped inside HTML spoiler tags like this: <tg-spoiler>hidden translation</tg-spoiler>.
- You can freely use parentheses, dashes, or normal text inside the spoiler tags without issues.

EXAMPLE FORMAT:
1. Mangiare
<tg-spoiler>essen - aß - gegessen</tg-spoiler>

2. La casa
<tg-spoiler>Das Haus</tg-spoiler>
"""

    @staticmethod
    def exercise_correction(exercise_context: str, student_answer: str) -> str:
        """Prompt to correct user's German translation solutions."""
        return f"""
You are a teacher of German language and you have to correct my exercises.

Here the Exercises:
{exercise_context}

Here my solutions to the excercises:
{student_answer}

Correct my exercises. The correction must be in the following format:
- First copy paste my response 
- Second, provide the corrected version. 
- Third, briefly explain the errors in a concise and brief way. 
Repeat it for every sentence. 
The explanations of the grammatical rules must be in Italian. Do not correct or explain anything if the response is alredy correct.
Do not repeat the context. Keep the response and the explanation as brief as possible. 
Make sure to only use what Telegram can correctly display and format.
"""
