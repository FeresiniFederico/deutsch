from datetime import date

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
        today_without_year = date.today().strftime("%B %d")
        # Rotate historical periods daily so the model explores different centuries
        eras = [
          "Antiquity or the Early Middle Ages (before 1000 AD)",
          "the High or Late Middle Ages (11th–15th century)",
          "the Renaissance or Early Modern period (16th–17th century)",
          "the 18th century (1701–1800)",
          "the 19th century (1801–1900)",
          "the early 20th century (1901–1945)",
          "the late 20th or 21st century (1946–present)",
        ]
        suggested_era = eras[date.today().timetuple().tm_yday % len(eras)]
        
        base_prompt = f"""
*** Task ***
Write a short, coherent paragraph in Italian (approximately 4 sentences) for me to translate into German. The text must be added good translation exercise for an A2 German language student. Use the following context to write the text:
** CONTEXT START**
{context}
** CONTEXT END **

*** Topic & Historical Inspiration ***
- Base the story on a real historical event that occurred on {today_without_year} in a past year (same month and day, different year).
- **Time Period Focus:** Prioritize an event from **{suggested_era}** on {today_without_year}. (Only fall back to an adjacent century if no notable event is recorded for that exact date in that era.)
- Briefly weave the historical year and event into the narrative so the context is clear.

*** Vocabulary & Grammar Constraints ***
- **80% Review:** Reuse as many words, verbs, and grammatical rules from the Learning Context above as possible.
- **20% New Vocabulary:** Introduce roughly 20% new words. For every word in the Italian text, immediately provide its German equivalent in parentheses, following this exact format:
  `[...] Italian word (German Translation) [...]`
German translation of verbs must be in the Infinitiv form, and adjectives and nouns neither konjugated, nor declinated.
- **Sentence Structure:** Use complex sentences with subordinate clauses and apply the grammar rules listed in the Learning Context.
- **Output Rule:** Provide ONLY the Italian exercise text. Do NOT include the full German translation.
"""
        if not is_friday:
            return base_prompt

        friday_extension = f"""
*** Friday Expansion (New Material) ***
1. **Additional Sentences:** Provide 2 extra sentences in German for me to translate into Italian. These sentences must introduce new vocabulary, verbs, and grammatical rules not yet present in the Learning Context.
2. **Brief Explanations:** Right after each German sentence, add a concise explanation in Italian covering the new words and grammar rules introduced in that sentence.

*** Context Update Requirement ***
At the very end of your response, output the exact marker:
{Prompts.MARKER_SUMMARY}

Immediately after this marker, output the **complete updated Learning Context** to be saved for future exercises:
- Start by copying the exact Learning Context provided at the top of this prompt word-for-word.
- Append the newly introduced vocabulary, verbs, and grammar rules from today's exercise to it.
- Do NOT rewrite, summarize, or omit anything from the original Learning Context—only append the new additions so nothing learned so far is lost.
"""
        return f"{base_prompt.strip()}\n\n{friday_extension.strip()}"

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

- First, provide the originak Italian sentence, part of the exercise.
- Second, copy paste my response 
- Third, provide the corrected version. 
- Fourth, explain the errors. 

Repeat it for every sentence. 
The explanations of the grammatical rules must be in Italian. Do not correct or explain anything if the response is alredy correct.
Do not repeat the context.
Make sure to only use what Telegram can correctly display and format.
"""
    @staticmethod
    def correction_study_guide_html(exercise_context: str, student_answer: str, correction_reply: str) -> str:
        return f"""
        You are a German teacher.
Based on the assigned exercise and the correction already provided, generate a complete, well-structured HTML document to be converted into a PDF as a comprehensive, full-lesson study guide organized by topic.
**Lesson Data**
**Exercise:**
{exercise_context}

**Correction Already Provided:**
{correction_reply}

** HTML Document Requirements **
- Return exclusively valid HTML code (from <!DOCTYPE html> to </html>), without markdown fences (```).
- Full-Lesson Depth per Topic: Group every mistake or weak point into distinct topic sections (e.g., verb conjugation, word order/syntax, grammatical cases, prepositions, articles/gender/plural, vocabulary/idioms). Even if a single verb is conjugated incorrectly or a rule is triggered only once, treat that entire topic as a full lesson from scratch—as if a professor were explaining the topic for the first time to a learner who has never seen it.
- Complete Reference Material in Every Section: For each topic section, include:
1. Clear conceptual explanation from first principles and why the mistake occurred in the exercise.
2. Explicit sentence structure rules and word-order patterns (where applicable, e.g., main clauses, subordinate clauses, verb brackets/Satzklammer, position of time/manner/place).
3. Complete reference tables—such as full conjugation tables across relevant tenses/persons for any misused or key verb, full declension/case tables, or structured grammar rules.
4. Multiple clear German examples paired with accurate Italian translations, highlighting what changed and why.
- Error Overview & Vocabulary Recap: Include a summary table mapping Mistake / Correct Form / Topic & Core Rule, plus a structured key vocabulary section (nouns with articles and plural forms, verbs with key forms, useful expressions).
- Print-Friendly Styling: Use a clean, well-proportioned internal <style> CSS optimized for PDF printing (@page margins, break-inside: avoid on tables and callout boxes where appropriate, readable typography, calm slate/blue accents, green for correct forms, amber/soft red for errors).
- Write all explanations and headings clearly in Italian, keeping German examples, grammatical terms where helpful, and translations clear and accurate.
""".strip()
