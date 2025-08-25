# encoding:utf-8

import json
import os
import random
import time

import plugins
from bridge.context import ContextType
from bridge.reply import Reply
from common.log import logger
from plugins import Event, EventAction, EventContext, Plugin


@plugins.register(
    name="Persona",
    desire_priority=99,
    hidden=False,
    desc="A plugin to give your bot a personality and human-like behavior",
    version="0.1",
    author="Gemini",
)
class Persona(Plugin):
    def __init__(self):
        super().__init__()
        try:
            '''# encoding:utf-8

import json
import os
import random
import time

import plugins
from bridge.context import Context, ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger
from plugins import Event, EventAction, EventContext, Plugin


@plugins.register(
    name="Persona",
    desire_priority=99,
    hidden=False,
    desc="A plugin to give your bot a personality and human-like behavior",
    version="0.3",
    author="Gemini",
)
class Persona(Plugin):
    def __init__(self):
        super().__init__()
        try:
            self.config = super().load_config()
            if not self.config:
                self.config = self._load_config_template()

            # Persona settings
            self.personality_prompt = self.config.get("personality_prompt", "")
            
            # Delay settings
            self.reply_delay_min = self.config.get("reply_delay_seconds", {}).get("min", 1)
            self.reply_delay_max = self.config.get("reply_delay_seconds", {}).get("max", 5)

            # Emotion settings
            emotion_conf = self.config.get("emotion_settings", {})
            self.emotions = emotion_conf.get("emotions", {"neutral": {}})
            self.current_emotion = emotion_conf.get("default_emotion", "neutral")

            # Memory settings
            memory_conf = self.config.get("memory_settings", {})
            self.memory_path = memory_conf.get("memory_path", "plugins/persona/memory")
            self.meta_analysis_prompt = memory_conf.get("meta_analysis_prompt", "")

            if not os.path.exists(self.memory_path):
                os.makedirs(self.memory_path)

            self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
            self.handlers[Event.ON_DECORATE_REPLY] = self.on_decorate_reply
            logger.info(f"[Persona] inited, current emotion: {self.current_emotion}")
        except Exception as e:
            logger.error(f"[Persona] initialization failed: {e}")
            raise f"[Persona] init failed, ignore "

    def on_handle_context(self, e_context: EventContext):
        if e_context["context"].type != ContextType.TEXT:
            return

        context = e_context["context"]
        
        # Behavior check based on emotion
        emotion_behavior = self.emotions.get(self.current_emotion, {})
        reply_probability = emotion_behavior.get("reply_probability", 1.0)
        if random.random() > reply_probability:
            logger.info(f"[Persona] Decided to ignore message based on emotion '{self.current_emotion}' (prob: {reply_probability})")
            e_context.action = EventAction.BREAK_PASS
            return

        # Store original content
        context["original_content"] = context.content
        
        # Load memory
        session_id = self._get_session_id(context)
        memory = self._load_memory(session_id)
        memory_prompt = "\n".join(f"- {fact}" for fact in memory)
        if memory_prompt:
            memory_prompt = f"[Memory]\n{memory_prompt}"

        # Inject persona, emotion, and memory into prompt
        question_rate = emotion_behavior.get("question_rate", 0.2)
        behavior_prompt = f"Your current emotion is {self.current_emotion}. You should ask questions with a probability of {question_rate}."
        
        new_content = (
            f"{self.personality_prompt}\n"
            f"{behavior_prompt}\n"
            f"{memory_prompt}\n
"
            f"[user]\n{context.content}"
        )
        context.content = new_content
        e_context.action = EventAction.CONTINUE

    def on_decorate_reply(self, e_context: EventContext):
        if e_context["reply"].type != ReplyType.TEXT:
            return

        # Perform meta-analysis for next turn
        self._perform_meta_analysis(e_context)

        # Apply reply delay
        delay = random.uniform(self.reply_delay_min, self.reply_delay_max)
        logger.info(f"[Persona] Delaying reply for {delay:.2f} seconds")
        time.sleep(delay)

        e_context.action = EventAction.CONTINUE

    def _perform_meta_analysis(self, e_context: EventContext):
        if not self.meta_analysis_prompt:
            return

        bot = e_context["bot"]
        if not bot:
            logger.warn("[Persona] Bot instance not found, skipping meta-analysis.")
            return

        try:
            context = e_context["context"]
            user_message = context.get("original_content", "")
            bot_reply = e_context["reply"].content
            
            prompt = self.meta_analysis_prompt.format(
                personality_prompt=self.personality_prompt,
                current_emotion=self.current_emotion,
                user_message=user_message,
                bot_reply=bot_reply,
                emotion_list=", ".join(self.emotions.keys())
            )

            meta_context = Context(type=ContextType.TEXT, content=prompt, msg=context['msg'])
            meta_reply = bot.reply(meta_context)
            
            if meta_reply and meta_reply.type == ReplyType.TEXT:
                self._process_meta_reply(meta_reply.content, context)
            else:
                logger.warn("[Persona] Failed to get a valid reply for meta-analysis.")

        except Exception as e:
            logger.error(f"[Persona] Failed to perform meta-analysis: {e}")

    def _process_meta_reply(self, reply_content: str, context: Context):
        try:
            # The LLM might return a markdown code block
            if "```json" in reply_content:
                reply_content = reply_content.split("```json")[1].split("```")[0]
            
            data = json.loads(reply_content)
            
            # Update emotion
            new_emotion = data.get("new_emotion")
            if new_emotion and new_emotion in self.emotions:
                self.current_emotion = new_emotion
                logger.info(f"[Persona] Emotion updated to: {self.current_emotion}")

            # Save facts to memory
            facts = data.get("facts_to_remember")
            if isinstance(facts, list) and len(facts) > 0:
                session_id = self._get_session_id(context)
                self._save_memory(session_id, facts)

        except json.JSONDecodeError:
            logger.warn(f"[Persona] Failed to decode JSON from meta-analysis reply: {reply_content}")
        except Exception as e:
            logger.error(f"[Persona] Error processing meta-analysis reply: {e}")

    def _get_session_id(self, context: Context) -> str:
        return context["session_id"]

    def _get_memory_path(self, session_id: str) -> str:
        return os.path.join(self.memory_path, f"{session_id}.json")

    def _load_memory(self, session_id: str) -> list:
        memory_file = self._get_memory_path(session_id)
        if os.path.exists(memory_file):
            try:
                with open(memory_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"[Persona] Failed to load memory for {session_id}: {e}")
        return []

    def _save_memory(self, session_id: str, new_facts: list):
        memory_file = self._get_memory_path(session_id)
        memory = self._load_memory(session_id)
        memory.extend(new_facts)
        try:
            with open(memory_file, "w", encoding="utf-8") as f:
                json.dump(memory, f, ensure_ascii=False, indent=4)
            logger.info(f"[Persona] Saved {len(new_facts)} new facts to memory for {session_id}")
        except Exception as e:
            logger.error(f"[Persona] Failed to save memory for {session_id}: {e}")

    def get_help_text(self, **kwargs):
        return "This plugin gives your bot a personality, manages its emotions and remembers conversations. Configure it in plugins/persona/config.json."

    def _load_config_template(self):
        logger.debug("No Persona plugin config.json, use plugins/persona/config.json.template")
        try:
            plugin_config_path = os.path.join(self.path, "config.json.template")
            if os.path.exists(plugin_config_path):
                with open(plugin_config_path, "r", encoding="utf-8") as f:
                    plugin_conf = json.load(f)
                    return plugin_conf
        except Exception as e:
            logger.exception(e)
            return {}
''

