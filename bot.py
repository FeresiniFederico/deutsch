import io
import os
import json
import time
import threading
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from gtts import gTTS
import gspread
from google import genai
from telebot import TeleBot
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

# Carica automaticamente le variabili dal file .env (utile sia da terminale che da systemd)
load_dotenv()
# --- CONFIGURAZIONE ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME")
SHEET_TAB_NAME = os.getenv("SHEET_TAB_NAME")
GEN_API_KEY = os.getenv("GEN_API_KEY")
CRED_FILE = os.getenv("CRED_FILE")

# File locale per tracciare l'ultima esecuzione riuscita
STATE_FILE = "last_run.json"
TIMEZONE = ZoneInfo("Europe/Rome")

# Inizializzazione Client
gc = gspread.service_account(filename=CRED_FILE)
client_genai = genai.Client(api_key=GEN_API_KEY)

# Inizializzazione Bot Telegram
bot = TeleBot(TELEGRAM_TOKEN)

def get_last_run_date():
    """Legge dal file locale la data dell'ultima esecuzione (formato YYYY-MM-DD)"""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
                return data.get("last_date")
        except Exception:
            pass
    return None

def save_last_run_date(date_str):
    """Salva sul file locale la data dell'ultima esecuzione"""
    try:
        with open(STATE_FILE, "w") as f:
            json.dump({"last_date": date_str}, f)
    except Exception as e:
        print(f"Errore nel salvataggio dello stato: {e}")

def invia_audio_da_testo(chat_id, testo, lingua='de'):
    """Converte un testo in audio MP3 e lo invia su Telegram."""
    if not testo:
        bot.send_message(chat_id, "⚠️ Non c'è nessun testo da convertire in audio.")
        return

    try:
        # Crea l'audio con gTTS (impostato su 'de' per il tedesco, o 'it' per l'italiano)
        tts = gTTS(text=testo, lang=lingua, slow=False)
        
        # Salva l'audio in un buffer in memoria (evita di creare file temporanei su disco)
        audio_buffer = io.BytesIO()
        tts.write_to_fp(audio_buffer)
        audio_buffer.seek(0)
        
        # Imposta un nome al file per Telegram
        audio_buffer.name = "esercizio.mp3"
        
        # Invia come messaggio vocale/audio su Telegram
        bot.send_audio(chat_id, audio_buffer, caption="🎧 Ecco l'audio dell'esercizio!")
        
    except Exception as e:
        print(f"Errore nella generazione/invio dell'audio: {e}")
        bot.send_message(chat_id, f"⚠️ Errore durante la creazione dell'audio: {e}")
        
def chiedi_a_gemini(testo):
    """Invia il testo a Gemini con logica di retry, fallback e un timeout di sicurezza."""
    modelli_da_provare =  ['gemini-4-carbon', 'gemini-4-argon', 'gemini-4-hydrogen', 'gemini-3.8-flash','gemini-3.6-flash', 'gemini-3.5-flash-lite', 'gemini-3.1-flash-lite']
    max_tentativi_per_modello = 2
    timeout_secondi = 60  # Se Gemini non risponde in 30 secondi, sblocca la chiamata

    def _chiama_api(modello, contenuto):
        response = client_genai.models.generate_content(
            model=modello,
            contents=contenuto,
        )
        return response.text

    for modello in modelli_da_provare:
        for tentativo in range(1, max_tentativi_per_modello + 1):
            try:
                print(f"[{modello}] Tentativo {tentativo} di chiamata a Gemini (timeout {timeout_secondi}s)...")
                
                # Eseguiamo la chiamata in un thread separato con un limite di tempo (timeout)
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(_chiama_api, modello, testo)
                    # .result(timeout=...) solleva Concurrent.futures.TimeoutError se scade il tempo
                    risposta_testo = future.result(timeout=timeout_secondi)
                    return risposta_testo

            except TimeoutError:
                print(f"[{modello}] ⏱️ Timeout scaduto! La chiamata a Gemini ha impiegato più di {timeout_secondi} secondi.")
            except Exception as e:
                errore_str = str(e)
                print(f"[{modello}] Tentativo {tentativo} fallito con errore: {errore_str}")
                
                if "high demand" in errore_str or "503" in errore_str or "429" in errore_str:
                    if tentativo < max_tentativi_per_modello:
                        tempo_attesa = tentativo * 5
                        print(f"Server sovraccarico. Attendo {tempo_attesa} secondi prima di riprovare...")
                        time.sleep(tempo_attesa)
                        continue
                break
                
    raise Exception("Tutti i tentativi con Gemini sono falliti o sono andati in timeout.")

def invia_messaggio_lungo(chat_id, testo, max_len=4000):
    """Spezza un testo lungo in chunk sicuri per Telegram e li invia in sequenza."""
    if not testo:
        return
    
    if len(testo) <= max_len:
        bot.send_message(chat_id, testo)
        return

    while len(testo) > 0:
        if len(testo) <= max_len:
            bot.send_message(chat_id, testo)
            break
        
        chunk = testo[:max_len]
        ultimo_a_capo = chunk.rfind('\n')
        
        if ultimo_a_capo > max_len // 2:
            split_index = ultimo_a_capo + 1
        else:
            split_index = max_len
            
        bot.send_message(chat_id, testo[:split_index])
        testo = testo[split_index:]
def gestisci_comando_audio(chat_id):
    """Legge Z10, interroga Gemini con un prompt personalizzato, converte la risposta in audio e la invia."""
    try:
        bot.send_message(chat_id, "🎙️ Elaborazione del testo con Gemini in corso...")
        
        # 1. Legge il contenuto dalla cella Z10
        sh = gc.open(SPREADSHEET_NAME)
        worksheet = sh.worksheet(SHEET_TAB_NAME)
        contenuto_z10 = worksheet.acell('Z10').value or ""
        
        if not contenuto_z10:
            bot.send_message(chat_id, "⚠️ La cella Z10 è vuota, nessun testo da elaborare.")
            return
        
        # 2. Prompt personalizzato per Gemini (puoi modificarlo come preferisci)
        prompt_gemini = f"""
        *** Exercise Context (A2 German Level) ***
        {contenuto_z10}

        Task: Translate the Italian text contained in the context above into German, suitable for an A2 German learner.

        CRITICAL INSTRUCTIONS:
        - Return ONLY and EXCLUSIVELY the German translation.
        - Do NOT include any introduction, greetings, explanations, notes, or concluding remarks.
        - Do NOT add phrases like "Here is the translation" or markdown code blocks unless it's strictly the translated text itself.
        - Keep it clean so it can be directly converted into a smooth audio message.
        """
        
        # 3. Chiamata a Gemini usando la tua funzione di retry esistente
        risposta_gemini = chiedi_a_gemini(prompt_gemini)
        
        if not risposta_gemini:
            bot.send_message(chat_id, "⚠️ Gemini non ha restituito alcuna risposta.")
            return

        bot.send_message(chat_id, "🔊 Conversione della risposta in audio in corso...")

        # 4. Converte la risposta testuale di Gemini in audio MP3 tramite gTTS
        # Nota: lang='de' leggerà con pronuncia tedesca, 'it' in italiano. 
        # Se il testo misto dà problemi, puoi impostare 'de' o 'it' in base alle tue preferenze.
        tts = gTTS(text=risposta_gemini, lang='de', slow=False)
        
        audio_buffer = io.BytesIO()
        tts.write_to_fp(audio_buffer)
        audio_buffer.seek(0)
        audio_buffer.name = "ripasso_gemini.mp3"
        
        # 5. Invia l'audio su Telegram (con una didascalia che mostra anche il testo elaborato da Gemini)
        didascalia = f"🎧 **Ripasso audio da Gemini:**\n\n{risposta_gemini}"
        # Telegram limita le didascalie a 1024 caratteri, tagliamo se necessario
        if len(didascalia) > 1024:
            didascalia = didascalia[:1020] + "..."
            
        bot.send_audio(chat_id, audio_buffer, caption=didascalia)
        
    except Exception as e:
        print(f"Errore nella generazione dell'audio con Gemini: {e}")
        bot.send_message(chat_id, f"⚠️ Errore durante la creazione dell'audio: {e}")
        
def task_mattutino():
    """Task mattutino con logica di retry (5 tentativi ogni 5 minuti)"""
    max_tentativi = 5
    attesa_secondi = 300  # 5 minuti
    
    for tentativo in range(1, max_tentativi + 1):
        try:
            print(f"[{datetime.now(TIMEZONE)}] Esecuzione task mattutino (Tentativo {tentativo}/{max_tentativi})...")
            
            # 1. Connessione al Google Sheet e lettura cella A2
            sh = gc.open(SPREADSHEET_NAME)
            worksheet = sh.worksheet(SHEET_TAB_NAME)
            contenuto_a2 = worksheet.acell('A10').value
            
            if not contenuto_a2:
                print("La cella A10 è vuota. Task completato senza invio.")
                oggi = datetime.now(TIMEZONE).strftime("%Y-%m-%d")
                save_last_run_date(oggi)
                return

            print(f"Letto da A10: ...")

            # 2. Gestione prompt dinamico (es. diverso il venerdì)
            adesso = datetime.now(TIMEZONE)
            if adesso.weekday() == 4: # Venerdì
                prompt = f"""
                   *** Context ***
                   {contenuto_a2}

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

                   Furthermore, provide 2 additional sentences in German to be translated into Italian, containing new vocabularies, verbs,
                   and grammatical rules, each followed by a brief explanation in Italian of the new words and the new grammar rules that must be added to the final summary
                   to keep track of what we've learnt so far day by day. Keep all corrections and explanations very concise.
                   At the end, you MUST include the exact phrase "--- ECCO IL RIASSUNTO ---", followed solely by the context you would copy to provide an LLM to move on with exercises 
                   that precisely incorporate all previously learned vocabulary, verbs, and grammatical rules you already find in the provided context at the beginning of this prompt, 
                   along with the new additions.
                   Make sure to update the CONTEXT already provided, always starts from there, update that one, do not create a new one from scratch, just copy the same context and add the verbs and words and grammar rules you want me to learn. 
                   ALWAYS UPDATE THE PROVIDED CONTEXT!
                """
            else:
                prompt = f"""
                   *** Context ***
                   {contenuto_a2}

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

            # 3. Invio a Gemini
            risposta_gemini = chiedi_a_gemini(prompt)


            # 5. Gestione del marker "-- ECCO IL RIASSUNTO --"
            marker = "--- ECCO IL RIASSUNTO ---"
            if marker in risposta_gemini:
                parti = risposta_gemini.split(marker, 1)
                testo_telegram = parti[0].strip()
                testo_a10 = parti[1].strip()

                # Scrive la parte successiva nella cella A10 del Google Sheet
                worksheet.update([[testo_a10]], 'A10')
                print("Testo successivo al marker salvato con successo in A10.")

                # Invia a Telegram solo la parte precedente
                if testo_telegram:
                    messaggio_finale = f"🌅{testo_telegram}"
                    invia_messaggio_lungo(TELEGRAM_CHAT_ID, messaggio_finale)
                    # 4. Scrittura della risposta completa in Z10
                    worksheet.update([[testo_telegram]], 'Z10')
                    print("Risposta completa salvata in Z10.")
            else:
                # Se il marker non è presente, invia tutto normalmente a Telegram
                messaggio_finale = f"🌅 {risposta_gemini}"
                invia_messaggio_lungo(TELEGRAM_CHAT_ID, messaggio_finale)
                # 4. Scrittura della risposta completa in Z10
                worksheet.update( [[risposta_gemini]], 'Z10')
                print("Risposta completa salvata in Z10.")
            
            # Successo! Salviamo la data odierna
            oggi = datetime.now(TIMEZONE).strftime("%Y-%m-%d")
            save_last_run_date(oggi)
            print("Task mattutino completato con successo.")
            return

        except Exception as e:
            errore_msg = str(e)
            print(f"Errore nel tentativo {tentativo}: {errore_msg}")
            
            if tentativo < max_tentativi:
                print(f"Nuovo tentativo tra 5 minuti...")
                time.sleep(attesa_secondi)
            else:
                print("Falliti tutti i 5 tentativi. Invio notifica di errore su Telegram.")
                try:
                    bot.send_message(
                        TELEGRAM_CHAT_ID, 
                        f"❌ **ERRORE CRITICO Task Mattutino**\n\nIl task delle 8:00 è fallito dopo 5 tentativi consecutivi.\n\n**Errore:**\n`{errore_msg}`"
                    )
                except Exception as telegram_err:
                    print(f"Impossibile inviare la notifica di errore su Telegram: {telegram_err}")

def gestisci_comando_flashcards(chat_id):
    """Genera Flashcards con spoiler HTML nativi di Telegram (evita errori di parsing)."""
    try:
        bot.send_message(chat_id, "🃏 Generazione delle Flashcards interattive in corso...")
        
        # 1. Legge il contesto attuale dalla cella A10
        sh = gc.open(SPREADSHEET_NAME)
        worksheet = sh.worksheet(SHEET_TAB_NAME)
        contenuto_a10 = worksheet.acell('A10').value or ""
        
        if not contenuto_a10:
            bot.send_message(chat_id, "⚠️ La cella A10 è vuota, impossibile generare le flashcards.")
            return
        
        # 2. Prompt ottimizzato per utilizzare i tag HTML <tg-spoiler>
        prompt_gemini = f"""
        *** Learning Context (German A2 Level) ***
        {contenuto_a10}

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
        
        # 3. Chiamata a Gemini
        risposta_gemini = chiedi_a_gemini(prompt_gemini)
        
        if not risposta_gemini:
            bot.send_message(chat_id, "⚠️ Gemini non ha restituito alcuna risposta per le flashcards.")
            return

        # 4. Invio a Telegram usando parse_mode="HTML"
        messaggio_finale = f"🃏 <b>Le tue Flashcards Interattive:</b>\n<i>(Clicca sui testi nascosti per svelare la traduzione)</i>\n\n{risposta_gemini}"
        
        bot.send_message(chat_id, messaggio_finale, parse_mode="HTML")
        
    except Exception as e:
        print(f"Errore nella generazione delle flashcards: {e}")
        bot.send_message(chat_id, f"⚠️ Errore durante la creazione delle flashcards: {e}")

# --- GESTIONE MESSAGGI TELEGRAM IN ARRIVO ---
@bot.message_handler(func=lambda message: True)
def handle_telegram_message(message):
    testo_utente = message.text.strip()
    chat_id = message.chat.id
    
    print(f"Messaggio ricevuto da Telegram ({chat_id}): {testo_utente}")
    
    try:
        # Se l'utente scrive "ancora", rilanciamo il task della mattina
        if testo_utente.lower() == "ancora":
            bot.reply_to(message, "🔄 Comando 'ancora' ricevuto. Avvio manuale del task mattutino...")
            # Lo facciamo partire in background per non bloccare il bot di Telegram
            threading.Thread(target=task_mattutino).start()
            return

        if testo_utente.lower() == "audio":
            bot.reply_to(message, "🎙️ Richiesta audio ricevuta. Elaborazione in corso...")
            threading.Thread(target=gestisci_comando_audio, args=(chat_id,)).start()
            return
            
            # Nota: imposta lang='it' se il testo in Z10 è principalmente in italiano, 
            # oppure 'de' se vuoi la pronuncia tedesca
            invia_audio_da_testo(chat_id, contenuto_z10, lingua='it')
            return

        if testo_utente.lower() == "context":
            sh = gc.open(SPREADSHEET_NAME)
            worksheet = sh.worksheet(SHEET_TAB_NAME)
            contenuto_a10 = worksheet.acell('A10').value or ""
            
            if not contenuto_a10:
                bot.send_message(chat_id, "⚠️ La cella A10 è attualmente vuota.")
            else:
                invia_messaggio_lungo(chat_id, f"📚 **Contesto attuale (Cella A10):**\n\n{contenuto_a10}")
            return

        if testo_utente.lower() in ["flashcards", "flashcard"]:
            bot.reply_to(message, "🃏 Preparazione delle flashcards dal contesto...")
            threading.Thread(target=gestisci_comando_flashcards, args=(chat_id,)).start()
            return

        # Altrimenti, leggiamo il contenuto della cella Z10 da Google Sheets
        sh = gc.open(SPREADSHEET_NAME)
        worksheet = sh.worksheet(SHEET_TAB_NAME)
        contenuto_z10 = worksheet.acell('Z10').value or ""
        
        print(f"Letto da Z10: {contenuto_z10}")

        # Prepariamo il prompt unendo il contesto di Z10 e la richiesta dell'utente
        prompt = f"""
            You are a teacher of German language and you have to correct my exercises.

            Here the Exercises:
            {contenuto_z10}

            Here my solutions to the excercises:
            {testo_utente}

            Correct my exercises. The correction must be in the following format:
            - First copy paste my response 
            - Second, provide the corrected version. 
            - Third, briefly explain the errors in a concise and brief way. 
            Repeat it for every sentence. 
           The explanations of the grammatical rules must be in Italian. Do not correct or explain anything if the response is alredy correct.
           Do not repeat the context. Keep the response and the explanation as brief as possible. 
           Make sure to only use what Telegram can correctly display and format.
        """

        # Inviamo il prompt a Gemini
        risposta_gemini = chiedi_a_gemini(prompt)

        # Inviamo la risposta a Telegram (spezzandola se supera i 4000 caratteri)
        invia_messaggio_lungo(chat_id, risposta_gemini)

    except Exception as e:
        errore_msg = str(e)
        print(f"Errore nella gestione del messaggio Telegram: {errore_msg}")
        bot.reply_to(message, f"⚠️ Errore nell'elaborazione della richiesta: {errore_msg}")

if __name__ == "__main__":

    adesso = datetime.now(TIMEZONE)
    oggi = adesso.strftime("%Y-%m-%d")
    ultimo_lancio = get_last_run_date()

    print(f"Avvio bot. Ultima esecuzione registrata: {ultimo_lancio} (Oggi è: {oggi})")

    if ultimo_lancio != oggi:
        if adesso.hour >= 8:
            print("L'orario delle 8:00 è già passato oggi e il task non è stato eseguito. Avvio immediato in corso...")
            import threading
            threading.Thread(target=task_mattutino).start()
        else:
            print("Il task non è ancora stato eseguito oggi, ma sono prima delle 8:00. Ci penserà lo scheduler.")

    scheduler = BackgroundScheduler(timezone=TIMEZONE)
    scheduler.add_job(task_mattutino, 'cron', hour=7, minute=0)
    scheduler.start()
    print("Scheduler avviato. Task programmato ogni giorno alle 08:00.")

    print("Bot Telegram in ascolto (Long Polling)...")
    try:
        bot.infinity_polling()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
